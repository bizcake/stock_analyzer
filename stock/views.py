from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView
from django.http import HttpResponseRedirect, JsonResponse
from django.core import serializers
from django.core.cache import cache
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.db.models import Q
from django.conf import settings
import json
import os

from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import StockMaster, MyTrackedStock, SignalCode, StockAnalysisLatest, StockAnalysisHistory
from .utils import analyze_batch_signals
from .services import StockAnalyzerService

# from .utils import get_category_briefing, get_signals_batch

import subprocess
from django.contrib import messages

def stock_analysis_view(request):
    priority = {
            # --- [1티어] 강력한 상승장 & 모멘텀 폭발 ---
            "🔥 초강력 매수 (반전)": 1,
            "🔥 강력 매수": 1,

            # --- [2티어] 추세 지속 및 폭발 임박 ---
            "↔️ 폭발 임박 (상방)": 2,
            "✅ 매수 (추세지속)": 2,

            # --- [3티어] 바닥 탈출 및 매수 타점 포착 ---
            "✅ 매수 (바닥탈출 시도)": 3,   # 추가됨 (최신 로직)
            "✅ 매수 (바닥탈출)": 3,        # (기존 호환용)
            "✅ 매수": 3,
            "📉 바닥 다지는 중 (매수 대기)": 4, # 추가됨: 하락장 속 강력한 수급 포착
            "📉 바닥 다지는 중 (관망)": 4,      # (기존 호환용)

            # --- [4티어] 단기 반등 및 횡보 (중립) ---
            "↔️ 기술적 반등 (저항주의)": 5,    # 추가됨: 하락장 속 데드캣 바운스
            "📉 기술적 반등 시도 (관망)": 5,   # 추가됨: 역배열 반등 초기
            "↔️ 방향 탐색 중": 6,
            "Hold (관망)": 6,

            # --- [5티어] 고점 의심 및 하락 경고 ---
            "⚠️ 관망 (단기 고점 의심)": 7,
            "⚠️ 매도 주의 (반등 끝자락)": 8,
            "↔️ 에너지 응축 (하방주의)": 8,
            "📉 바닥 확인 중 (관망)": 8,

            # --- [6티어] 하락장 및 매도 ---
            "📉 하락 추세 지속 (관망)": 9,     # 추가됨 (최신 로직)
            "📉 매도 (추세이탈)": 10,
            "📉 매도": 10,

            # --- [7티어] 시스템 및 통신 에러 (항상 맨 아래로) ---
            "조회 실패": 11,
            "다운로드 실패": 11,             # 추가됨 (청크 스캔 에러)
            "Rate Limit(차단)": 12,          # 추가됨 (야후 차단 에러)
            "데이터 차단/부족": 12,          # 추가됨 (청크 스캔 에러)
            "데이터 부족": 13
        }

    user_name = request.POST.get("user_name", "현욱").strip()
    target_category = request.POST.get("target_category")
    results = {}
    master_json_str = ""

    master_file = os.path.join(settings.BASE_DIR, f'stocks_{user_name}.json')
    result_file = os.path.join(settings.BASE_DIR, f'result_{user_name}.json')

    if user_name and os.path.exists(master_file):
        with open(master_file, 'r', encoding='utf-8') as f:
            master_json_str = f.read()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_json":
            new_json_data = request.POST.get("json_data")
            try:
                parsed_data = json.loads(new_json_data)
                with open(master_file, 'w', encoding='utf-8') as f:
                    json.dump(parsed_data, f, ensure_ascii=False, indent=4)
                return JsonResponse({"status": "success", "message": "✅ 저장되었습니다."})
            except json.JSONDecodeError:
                return JsonResponse({"status": "error", "message": "❌ 형식이 잘못되었습니다."}, status=400)

        elif action == "analyze":
            if not os.path.exists(master_file):
                results = {"error": "종목 리스트 파일이 없습니다."}
            else:
                # 1. 마스터 파일 및 기존 결과 로드
                with open(master_file, 'r', encoding='utf-8') as f:
                    stocks_to_analyze = json.load(f)

                results = {}
                if os.path.exists(result_file):
                    with open(result_file, 'r', encoding='utf-8') as f:
                        results = json.load(f)

                # 2. 분석할 티커 리스트 수집 (중복 제거)
                target_tickers = []
                for cat, ticker_dict in stocks_to_analyze.items():
                    # 특정 카테고리만 분석할 경우 필터링, 아니면 전체 수집
                    if not target_category or cat == target_category:
                        target_tickers.extend(ticker_dict.values())

                target_tickers = list(set(target_tickers))

                # 3. 배치 분석 실행 (딱 한 번만 호출)
                all_signals = ''#get_signals_batch(target_tickers)

                # 4. 배치 결과를 기존 results 구조에 매핑
                for category, ticker_dict in stocks_to_analyze.items():
                    if target_category and category != target_category:
                        continue

                    results[category] = [] # 해당 카테고리 초기화
                    for name, ticker in ticker_dict.items():
                        # 배치 결과에서 데이터 가져오기 (없으면 기본값)
                        res = all_signals.get(ticker, {"price": 0, "signal": "데이터 부족", "exchange": "UNKNOWN"})

                        mapping = {"NYQ": ".N", "ASE": ".A", "PCX": ".A", "NMS": ".O", "NGM": ".O"}
                        suffix = mapping.get(res.get('exchange'), ".O")

                        results[category].append({
                            "name": name,
                            "ticker": ticker,
                            "naver_url": res.get('naver_url'),
                            "trend_url": res.get('trend_url'), # trend view
                            "trend_label": res.get('trend_label'),
                            "trend_color": res.get('trend_color'),
                            "trend_direction": res.get('trend_direction'),
                            "trend_count": res.get('trend_count'),
                            "price": res.get('price', 0),
                            "signal": res.get('signal', '조회 실패'),
                            "exchange": res.get('exchange', 'UNKNOWN')
                        })

                    # 정렬
                    results[category].sort(key=lambda x: priority.get(x['signal'], 99))

                # 5. 파일 캐시 저장
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=4)

    else: # GET 요청
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                for cat in results:
                    if isinstance(results[cat], list):
                        results[cat].sort(key=lambda x: priority.get(x['signal'], 99))

    return render(request, 'stock/stock_analysis.html', {
        'results': results,
        'user_name': user_name,
        'master_json_str': master_json_str,
        'target_category': target_category
    })

def api_category_briefing(request):
    category = request.GET.get('category')
    user_name = request.GET.get('user_name', '현욱')

    # 기존 분석 결과 파일에서 해당 카테고리 데이터 로드
    result_file = os.path.join(settings.BASE_DIR, f'result_{user_name}.json')

    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
            stock_list = all_results.get(category, [])

        if not stock_list:
            return JsonResponse({"status": "error", "message": "분석된 종목 데이터가 없습니다."})

        briefing = get_category_briefing(category, stock_list)
        return JsonResponse({"status": "success", "briefing": briefing})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

# 프로젝트 절대 경로 및 스크립트 파일명 설정
PROJECT_DIR = "/home/batteryz1999/stocks/stock/"
BOT_SCRIPT = "telegram_notifier.py"
LOG_FILE = os.path.join(PROJECT_DIR, "bot.log") # 💡 로그 파일 경로 추가

def check_bot_is_running():
    """ps 명령어로 실제 프로세스가 메모리에 떠 있는지 직접 검사"""
    try:
        # grep -v grep: grep 명령어 자체의 프로세스는 검색 결과에서 제외하는 필수 테크닉
        command = f"ps aux | grep {BOT_SCRIPT} | grep -v grep"
        output = subprocess.check_output(command, shell=True, text=True)

        # 출력 결과가 있다면 프로세스가 돌고 있다는 뜻
        return len(output.strip()) > 0

    except subprocess.CalledProcessError:
        # grep이 매칭되는 프로세스를 찾지 못하면 에러(종료 코드 1)를 발생시킵니다.
        return False

def bot_dashboard(request):
    """봇 상태 확인 대시보드 화면"""
    is_running = check_bot_is_running()

    # 💡 로그 파일 읽어오기 로직 추가
    logs = "아직 기록된 로그가 없습니다."
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 최신 로그 20줄만 잘라서 화면에 전달 (파일이 커져도 문제없음)
                logs = "".join(lines[-20:]) if lines else "로그가 비어있습니다."
        except Exception as e:
            logs = f"로그 파일을 읽는 중 에러가 발생했습니다: {e}"

    return render(request, "stock/bot_dashboard.html", {"is_running": is_running,'logs':logs})

def start_bot(request):
    """봇을 백그라운드로 실행"""
    if not check_bot_is_running():
        try:
            # 절대 경로 조합
            script_path = os.path.join(PROJECT_DIR, BOT_SCRIPT)
            # 💡 로그 파일을 'a' (이어쓰기) 모드로 열기
            log_out = open(LOG_FILE, "a", encoding="utf-8")

            subprocess.Popen(
                ["/home/batteryz1999/.venv/bin/python", script_path],
                cwd=PROJECT_DIR,
                stdout=log_out,
                stderr=log_out
            )
            messages.success(request, "🚀 텔레그램 봇 스케줄러를 성공적으로 시작했습니다.")
        except Exception as e:
            messages.error(request, f"❌ 봇 실행 실패: {e}")
    else:
        messages.warning(request, "⚠️ 봇이 이미 실행 중입니다.")

    return redirect('stock:bot_dashboard')

def stop_bot(request):
    """pkill을 사용하여 스크립트 이름으로 프로세스 강제 종료"""
    if check_bot_is_running():
        try:
            # pkill -f: 프로세스 이름이나 인자(argument)를 검색해서 종료
            command = f"pkill -f {BOT_SCRIPT}"
            subprocess.run(command, shell=True, check=True)

            # (선택) 중지 시 로그에 중지되었다는 기록 남기기
            with open(LOG_FILE, "a", encoding="utf-8") as log_out:
                log_out.write("\n[System] 봇 프로세스가 강제 종료되었습니다.\n")

            messages.success(request, "🛑 텔레그램 봇이 완전히 중지되었습니다.")
        except subprocess.CalledProcessError:
            messages.error(request, "❌ 봇을 중지하는 과정에서 에러가 발생했습니다.")

    return redirect('bot_dashboard')


def search_stock_api(request):
    """종목 검색 API (Ajax 용)"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    # 티커, 한글명, 영문명으로 검색 (최대 20개 제한)
    stocks = StockMaster.objects.filter(
        Q(ticker__icontains=query) |
        Q(name_kr__icontains=query) |
        Q(name_en__icontains=query)
    )[:20]

    results = [
        {'id': s.id, 'ticker': s.ticker, 'name': s.name_kr or s.name_en, 'market': s.market}
        for s in stocks
    ]
    return JsonResponse({'results': results})

# def add_tracked_stock(request, stock_id):
#     """모니터링 대상 추가"""
#     stock = get_object_or_404(StockMaster, id=stock_id)
#     TrackedStock.objects.get_or_create(stock=stock)
#     return redirect('stock:bot_dashboard') # 본인의 대시보드 URL 네임으로 변경

# def remove_tracked_stock(request, stock_id):
#     """모니터링 대상 삭제"""
#     TrackedStock.objects.filter(stock_id=stock_id).delete()
#     return redirect('stock:bot_dashboard')


from .models import StockMaster, MyTrackedStock, StockAnalysisLatest, SignalCode

def dashboard_view(request):
    """DB에 저장된 최신 분석 결과를 바로 조회하여 전달 (스케줄러 연동)"""
    
    # 1. 툴팁용 시그널 공통코드 가져오기
    signal_map = {sc.code: {'name': sc.name, 'desc': sc.description} for sc in SignalCode.objects.all()}

    # 2. 내 관심종목 조회
    my_stocks = MyTrackedStock.objects.select_related('stock', 'stock__latest_analysis').all()

    categorized_stocks = {'KR': [], 'US': [], 'COIN': []}
    tv_base = "https://www.tradingview.com/chart/aFDVPmY7/"

    for item in my_stocks:
        stock = item.stock
        analysis = getattr(stock, 'latest_analysis', None)

        market = stock.market
        actual_exchange = stock.exchange.upper() if stock.exchange else ''

        if market == 'COIN':
            clean_ticker = stock.ticker.replace("-USD", "").replace("KRW-", "")
            trend_url = f"{tv_base}?symbol=BINANCE:{clean_ticker}USDT"
            naver_url = f"https://m.stock.naver.com/fchart/crypto/UPBIT/{clean_ticker}"
            
        elif market in ['KR', 'KOSPI', 'KOSDAQ']: # 혹시 모를 기존 KR 데이터 호환
            code = stock.ticker.split('.')[0]
            trend_url = f"{tv_base}?symbol=KRX:{code}"
            naver_url = f"https://m.stock.naver.com/fchart/domestic/stock/{code}"
            
        else: 
            # 3. 🚀 대망의 미국 주식(US) 링크 완벽 분기 처리
            if actual_exchange == 'NASDAQ':
                # 나스닥은 네이버에 .O 를 붙임
                trend_url = f"{tv_base}?symbol=NASDAQ:{stock.ticker}"
                naver_url = f"https://m.stock.naver.com/fchart/foreign/stock/{stock.ticker}.O"
            elif actual_exchange == 'AMEX':
                # 아멕스는 트레이딩뷰 AMEX 심볼 사용, 네이버는 .O 안 붙임
                trend_url = f"{tv_base}?symbol=AMEX:{stock.ticker}"
                naver_url = f"https://m.stock.naver.com/fchart/foreign/stock/{stock.ticker}"
            else:
                # NYSE 및 그 외 거래소는 범용적으로 NYSE 심볼 사용, 네이버는 .O 안 붙임
                trend_url = f"{tv_base}?symbol=NYSE:{stock.ticker}"
                naver_url = f"https://m.stock.naver.com/fchart/foreign/stock/{stock.ticker}"

        # --- 시그널 데이터 및 딕셔너리 매핑 (기존과 완전히 동일) ---
        code = analysis.signal_code if analysis and analysis.signal_code else 'd01'

        stock_data = {
            'id': stock.id,
            'name_kr': stock.name_kr,
            'ticker': stock.ticker,
            'ticker_clean': stock.ticker.split('.')[0], # 복사용 깔끔한 티커
            't_signal': analysis.t_signal if analysis else 'gray',
            'n_signal': analysis.n_signal if analysis else 'gray',
            'c_signal': analysis.c_signal if analysis else 'gray',
            'p_name': analysis.p_name if analysis else '대기중',
            'up_days': analysis.up_days if analysis else 0,
            'signal_code': code,
            'signal_name': signal_map.get(code, {}).get('name', 'Hold (관망)'),
            'signal_desc': signal_map.get(code, {}).get('desc', '분석 대기중입니다.'),
            'trend_url': trend_url,
            'naver_url': naver_url
        }

        if market in categorized_stocks:
            categorized_stocks[market].append(stock_data)

    # 3. 🚀 시그널 코드(a01 -> d01) 순서로 명확하게 정렬 (강력 매수가 맨 위로)
    for mkt in categorized_stocks:
        categorized_stocks[mkt].sort(key=lambda x: x['signal_code'])

    return render(request, 'stock/dashboard.html', {'categorized_stocks': categorized_stocks})

@csrf_exempt
def api_run_batch_analysis(request):
    """
    모든 관심 종목을 야후에서 한 번에 가져와서 일괄 분석 및 DB 저장 (Service Layer 활용)
    """
    if request.method == "POST":
        target_market = request.POST.get('market') # 'KR', 'US', 'COIN'
        
        # 1. 서비스 호출하여 분석 및 DB 저장 수행
        # 특정 마켓이 지정되면 해당 마켓만, 아니면 전체 관심 종목 분석
        success_count = StockAnalyzerService.run_analysis(market=target_market)

        if success_count == 0:
            return JsonResponse({"status": "error", "message": "분석할 종목이 없거나 데이터 다운로드에 실패했습니다."})

        # 2. 화면 갱신을 위해 최신 분석 결과를 다시 읽어옴
        # (주의: StockAnalyzerService에서 이미 DB 업데이트를 완료함)
        my_stocks = MyTrackedStock.objects.select_related('stock', 'stock__latest_analysis')
        if target_market:
            my_stocks = my_stocks.filter(stock__market=target_market)
            
        response_data = {}
        for item in my_stocks:
            analysis = getattr(item.stock, 'latest_analysis', None)
            if analysis:
                response_data[item.stock.id] = {
                    't_signal': analysis.t_signal,
                    'n_signal': analysis.n_signal,
                    'c_signal': analysis.c_signal,
                    'p_name': analysis.p_name,
                    'up_days': analysis.up_days,
                    'signal_code': analysis.signal_code,
                }

        return JsonResponse({
            "status": "success", 
            "results": response_data,
            "message": f"총 {success_count}개 종목 분석 및 DB 저장 완료!"
        })
    
# 🟢 1. [조회] 및 [마스터 DB 강제 등록]
@csrf_exempt
def api_search_and_add(request):
    if request.method == "POST":
        action = request.POST.get('action')
        
        # [조회 기능] 팝업에서 검색어 입력 시
        if action == 'search':
            keyword = request.POST.get('keyword', '').strip()
            # 한글명 또는 티커로 검색
            stocks = StockMaster.objects.filter(name_kr__icontains=keyword) | StockMaster.objects.filter(ticker__icontains=keyword)
            data = [{"id": s.id, "ticker": s.ticker, "name": s.name_kr, "market": s.market} for s in stocks[:10]]
            return JsonResponse({"results": data})
            
        # [등록 기능 1] 검색해도 안 나올 때, 마스터 DB에 아예 새로 등록
        elif action == 'add_master':
            ticker = request.POST.get('ticker')
            name = request.POST.get('name')
            market = request.POST.get('market')
            stock, created = StockMaster.objects.get_or_create(ticker=ticker, defaults={'name_kr': name, 'market': market})
            return JsonResponse({"status": "success", "id": stock.id})

# 🔵 2. 내 관심종목 [등록] 및 [삭제]
@csrf_exempt
def api_manage_tracked(request):
    if request.method == "POST":
        stock_id = request.POST.get('stock_id')
        action = request.POST.get('action')
        stock = StockMaster.objects.get(id=stock_id)
        
        # [등록 기능 2] 검색된 종목을 '내 대시보드'에 추가할 때
        if action == 'add':
            MyTrackedStock.objects.get_or_create(stock=stock)
            
        # [삭제 기능] 대시보드 화면에서 '삭제' 버튼을 눌렀을 때
        elif action == 'delete':
            MyTrackedStock.objects.filter(stock=stock).delete()
            
        return JsonResponse({"status": "success"})