import requests
import yfinance as yf
from stock.models import StockDailyChart
from django.db.models import Max
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db import transaction


def _make_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })
    return session

def _fetch_and_save(ticker, session, mode='incremental', index=''):
    """
    mode:
      'full'        - 3년치 전체
      'incremental' - 마지막 날짜 기준 증분
      'today'       - 오늘 하루만
    """
    try:
        stock = yf.Ticker(ticker, session=session)

        if mode == 'full':
            history = stock.history(period="3y", auto_adjust=True)

        elif mode == 'today':
            history = stock.history(period="5d", auto_adjust=True)
            # 오늘 날짜만 필터
            from datetime import date
            history = history[history.index.date == date.today()]

        else:  # incremental
            last_date = (
                StockDailyChart.objects
                .filter(stock_id=ticker)
                .aggregate(max_date=Max('date'))['max_date']
            )
            if not last_date:
                # 증분인데 데이터 없으면 전체 수집으로 전환
                history = stock.history(period="3y", auto_adjust=True)
                mode = 'full(fallback)'
            else:
                start_date = last_date - timedelta(days=7)
                history = stock.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    auto_adjust=True
                )

        if history.empty:
            print(f"[{index}] {ticker} 데이터 없음")
            return

        history = history.dropna()
        history.index = history.index.date
        records = history[['Open','High','Low','Close','Volume']].to_dict('index')

        objects = [
            StockDailyChart(
                stock_id    = ticker,
                date        = date_val,
                open_price  = Decimal(str(round(row['Open'],  4))),
                high_price  = Decimal(str(round(row['High'],  4))),
                low_price   = Decimal(str(round(row['Low'],   4))),
                close_price = Decimal(str(round(row['Close'], 4))),
                adj_close   = Decimal(str(round(row['Close'], 4))),
                volume      = int(row['Volume']),
            )
            for date_val, row in records.items()
        ]

        if objects:
            with transaction.atomic():
                StockDailyChart.objects.bulk_create(
                    objects,
                    update_conflicts=True,
                    unique_fields=['stock', 'date'],
                    update_fields=[
                        'open_price','high_price','low_price',
                        'close_price','adj_close','volume'
                    ]
                )
            print(f"[{index}] {ticker} [{mode}] {len(objects)}건 완료")

    except Exception as e:
        print(f"[{index}] {ticker} 오류: {e}")


def _fetch_and_save_batch(ticker_list, mode='incremental', batch_index=''):
    """
    50개 종목을 한 번에 API 호출하여 저장 (수정해주신 로직 통합)
    """
    try:
        # 1. 호출 기간 설정
        if mode == 'full':
            params = {"period": "3y"}
        elif mode == 'today':
            params = {"period": "7d"} # 여유있게 가져와서 당일 필터링
        else: # incremental
            # 증분은 종목별 마지막 날짜가 다를 수 있으므로 
            # 배치 내 가장 오래된 '마지막 날짜' 기준으로 조회하거나 넉넉히 1개월치 조회
            params = {"period": "1mo"} 

        # 2. 일괄 다운로드 (session 제외하여 에러 방지)
        # group_by='ticker' 필수: 종목별 데이터 분리 용이
        df_all = yf.download(
            ticker_list, 
            **params, 
            auto_adjust=True, 
            group_by='ticker', 
            progress=False
        )

        if df_all.empty:
            print(f"[{batch_index}] 데이터 없음")
            return

        # 3. 종목별 루프
        for ticker in ticker_list:
            try:
                # 단일 종목과 다중 종목 결과 구조 대응
                df = df_all[ticker].copy() if len(ticker_list) > 1 else df_all.copy()
                df = df.dropna()
                
                if mode == 'today':
                    df = df[df.index.date == date.today()]
                
                if df.empty: continue

                # 작성하신 데이터 가공 로직 적용
                df.index = df.index.date
                records = df[['Open','High','Low','Close','Volume']].to_dict('index')

                objects = [
                    StockDailyChart(
                        stock_id    = ticker,
                        date        = date_val,
                        open_price  = Decimal(str(round(row['Open'],  4))),
                        high_price  = Decimal(str(round(row['High'],  4))),
                        low_price   = Decimal(str(round(row['Low'],   4))),
                        close_price = Decimal(str(round(row['Close'], 4))),
                        adj_close   = Decimal(str(round(row['Close'], 4))), # auto_adjust=True 결과물
                        volume      = int(row['Volume']),
                    )
                    for date_val, row in records.items()
                    if int(row['Volume']) > 0  # ✅ 거래량 0인 날 자동 제외 (거래정지일)
                ]

                if objects:
                    with transaction.atomic():
                        StockDailyChart.objects.bulk_create(
                            objects,
                            update_conflicts=True,
                            unique_fields=['stock', 'date'],
                            update_fields=[
                                'open_price','high_price','low_price',
                                'close_price','adj_close','volume'
                            ]
                        )
            except Exception as e:
                print(f"[{ticker}] 개별 저장 오류: {e}")

        print(f"[{batch_index}] {len(ticker_list)}개 종목 배치 처리 완료")

    except Exception as e:
        print(f"[{batch_index}] 배치 전체 오류: {e}")