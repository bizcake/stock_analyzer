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
                all_signals = {} # 더 이상 사용하지 않는 레거시 뷰의 에러 방지용

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

def dashboard_view(request):
    """DB에 저장된 최신 분석 결과를 바로 조회하여 전달 (스케줄러 연동)"""
    
    # 1. 툴팁용 시그널 공통코드 가져오기
    signal_map = {sc.code: {'name': sc.name, 'desc': sc.description} for sc in SignalCode.objects.all()}

    # 2. 내 관심종목 조회
    my_stocks = MyTrackedStock.objects.select_related('stock', 'stock__latest_analysis').all()

    categorized_stocks = {'KR': [], 'US': [], 'COIN': []}

    for item in my_stocks:
        stock = item.stock
        analysis = getattr(stock, 'latest_analysis', None)

        market = stock.market
        trend_url = stock.tv_url
        naver_url = stock.naver_url

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
