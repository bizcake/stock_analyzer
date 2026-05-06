import time
import requests
import yfinance as yf
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Max, Min
from django.db import transaction
# 본인 프로젝트에 맞게 경로 수정
from stock.models import StockMaster, StockDailyChart
from datetime import datetime
import pytz
from .utils import _make_session, _fetch_and_save, _fetch_and_save_batch

def sync_initial_full(batch_size=50, batch_delay=1.0):
    """
    최초 1회 실행 - 데이터 없는 종목만 3년치 수집
    batch_size: 한 번에 처리할 종목 수
    """
    print("🚀 최초 전체 수집 시작...")
    # 이미 데이터 있는 종목 제외
    # existing_tickers = set(
    #     StockDailyChart.objects.values_list('stock_id', flat=True).distinct()
    # )
    # 1. 기준일 계산: 오늘로부터 100일 전 날짜
    # (DateField를 사용 중이라면 .date()를 붙여주고, DateTimeField라면 그대로 사용하세요)
    threshold_date = timezone.now().date() - timedelta(days=100)

    # 2. 충분한 데이터가 있는 종목 찾기 (가장 오래된 날짜가 100일 전이거나 그 이전인 종목)
    # 날짜 필드 이름이 'date'라고 가정 (실제 모델의 날짜 필드명으로 수정 필요)
    sufficient_data_qs = StockDailyChart.objects.values('stock_id').annotate(
        min_date=Min('date')
    ).filter(min_date__lte=threshold_date)

    # 100일 치 이상을 보유한 기업들의 집합
    existing_tickers = set(sufficient_data_qs.values_list('stock_id', flat=True))
    
    all_tickers = list(StockMaster.objects
                       .filter(index_type__isnull=False)
                       .values_list('ticker', flat=True))
    new_tickers  = [t for t in all_tickers if t not in existing_tickers]

    print(f"신규 수집 대상: {len(new_tickers)}개")
    print(new_tickers)

    session = _make_session()

    total_count = len(new_tickers)
    for i in range(0, total_count, batch_size):
        batch_list = new_tickers[i:i+batch_size]
        current_batch_num = i // batch_size + 1
        
        print(f"\n📦 [배치 {current_batch_num}] {len(batch_list)}개 종목 수집 시작...")

        print(f"🚀 신규 수집 대상: {total_count}개")
        # 일괄 수집 및 저장 함수 호출
        _fetch_and_save_batch(batch_list, mode='full')

        # IP 차단 방지를 위한 배치 간 대기 (50건 호출 후 휴식)
        if i + batch_size < total_count:
            print(f"💤 배치 완료. {batch_delay}초 대기 중... ({i+len(batch_list)}/{total_count})")
            time.sleep(batch_delay)

        # 배치 완료 후 추가 대기 (IP 차단 방지)
        print(f"배치 완료. 30초 대기...")
        time.sleep(10)

def sync_intraday_today(batch_size=95, batch_delay=3.0, target_markets=None):
    """
    장중 1시간마다 실행 - 당일 데이터 갱신 (배치 방식)
    """

    if target_markets == None :
        target_markets.append('KR')
        target_markets.append('US')
        target_markets.append('COIN')

    # 대상 티커 추출
    tickers = list(
        StockMaster.objects
                    .filter(index_type__isnull=False)
                    .filter(market__in=target_markets)
                    .values_list('ticker', flat=True)
    )

    total_count = len(tickers)
    print(f"🕒 장중 갱신 대상: {total_count}개 ({target_markets})")

    # 50개씩 배치 처리
    for i in range(0, total_count, batch_size):
        batch_list = tickers[i : i + batch_size]
        batch_idx_str = f"{i + len(batch_list)}/{total_count}"

        print(f"\n⚡ [실시간 배치 {i//batch_size + 1}] 갱신 중... ({batch_idx_str})")
        print(batch_list)
        # mode='today'로 호출하여 당일 데이터 위주로 UPSERT
        _fetch_and_save_batch(batch_list, mode='today', batch_index=batch_idx_str)

        # 장중에는 빠른 갱신을 위해 딜레이를 짧게 가져감
        if i + batch_size < total_count:
            time.sleep(batch_delay)

    print("\n✅ 장중 실시간 데이터 갱신 완료.")

# if __name__ == '__main__':
#     sync_intraday_today()

# 사용안함
# @DeprecationWarning
# def sync_daily_update(batch_size=50, batch_delay=5.0):
#     """
#     매일 장마감 후 1회 실행 - 증분 업데이트 (배치 방식)
#     """
#     from datetime import date
#     today = date.today()

#     # 1. 오늘 이미 데이터가 있는 종목 스킵
#     already_updated = set(
#         StockDailyChart.objects.filter(date=today)
#         .values_list('stock_id', flat=True)
#     )

#     # 2. 업데이트 대상 티커 추출 (index_type 조건 포함 등 기존 필터 유지 가능)
#     tickers = list(
#         StockMaster.objects.exclude(ticker__in=already_updated)
#         .values_list('ticker', flat=True)
#     )

#     total_count = len(tickers)
#     print(f"🚀 증분 업데이트 대상: {total_count}개")

#     if not tickers:
#         print("모든 종목이 최신 상태입니다.")
#         return

#     # 3. 50개씩 배치 처리
#     for i in range(0, total_count, batch_size):
#         batch_list = tickers[i : i + batch_size]
#         batch_idx_str = f"{i + len(batch_list)}/{total_count}"
        
#         print(f"\n📦 [배치 {i//batch_size + 1}] 데이터 수집 중... ({batch_idx_str})")
        
#         # 앞서 구현한 배치 저장 함수 호출
#         _fetch_and_save_batch(batch_list, mode='incremental', batch_index=batch_idx_str)

#         # 배치 간 짧은 휴식 (API 안정성 확보)
#         if i + batch_size < total_count:
#             time.sleep(batch_delay)

#     print("\n✅ 일일 증분 업데이트 완료.")

# def sync_stock_daily_charts():
#     session = requests.Session()
#     session.headers.update({
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
#     })

#     tickers = list(StockMaster.objects.values_list('ticker', flat=True))
#     total_count = len(tickers)

#     # stock_id = ticker (to_field='ticker' 이므로 정상)
#     last_dates_qs = StockDailyChart.objects.values('stock_id').annotate(max_date=Max('date'))
#     last_dates = {item['stock_id']: item['max_date'] for item in last_dates_qs}

#     for index, ticker in enumerate(tickers, start=1):
#         ticker_objects = []  # ✅ 종목 단위로 초기화
#         last_date = last_dates.get(ticker)

#         try:
#             stock = yf.Ticker(ticker, session=session)

#             if not last_date:
#                 history = stock.history(period="3y", auto_adjust=True)
#                 mode = "신규 3년"
#             else:
#                 start_date = last_date - timedelta(days=7)
#                 history = stock.history(
#                     start=start_date.strftime('%Y-%m-%d'),
#                     auto_adjust=True
#                 )
#                 mode = f"증분({start_date}~)"

#             if history.empty:
#                 print(f"[{index}/{total_count}] {ticker} 데이터 없음")
#                 continue

#             history = history.dropna()

#             # ✅ iterrows 대신 to_dict로 성능 개선
#             history.index = history.index.date
#             records = history[['Open','High','Low','Close','Volume']].to_dict('index')

#             for date_val, row in records.items():
#                 ticker_objects.append(
#                     StockDailyChart(
#                         stock_id=ticker,
#                         date=date_val,
#                         open_price=Decimal(str(round(row['Open'],   4))),
#                         high_price=Decimal(str(round(row['High'],   4))),
#                         low_price =Decimal(str(round(row['Low'],    4))),
#                         close_price=Decimal(str(round(row['Close'], 4))),
#                         adj_close  =Decimal(str(round(row['Close'], 4))),
#                         volume=int(row['Volume']),
#                     )
#                 )

#             # ✅ 종목 단위로 UPSERT
#             if ticker_objects:
#                 with transaction.atomic():
#                     StockDailyChart.objects.bulk_create(
#                         ticker_objects,
#                         update_conflicts=True,
#                         unique_fields=['stock', 'date'],
#                         update_fields=[
#                             'open_price','high_price','low_price',
#                             'close_price','adj_close','volume'
#                         ]
#                     )
#                 print(f"[{index}/{total_count}] {ticker} {mode} {len(ticker_objects)}건 완료")

#         except Exception as e:
#             print(f"[{index}/{total_count}] {ticker} 오류: {e}")

#         finally:
#             time.sleep(0.5)  # ✅ 예외 여부 무관하게 항상 실행