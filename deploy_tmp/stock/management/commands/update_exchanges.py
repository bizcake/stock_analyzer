import time
import random
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from django.db.models import Q
from stock.models import StockMaster

class Command(BaseCommand):
    help = '야후 파이낸스의 차단을 피하기 위해 속도를 조절하고 에러 시 재시도(Retry)합니다.'

    def fetch_exchange(self, ticker, retries=3):
        """야후 서버 차단을 피하기 위한 재시도(Retry) 및 랜덤 딜레이 적용 함수"""
        for attempt in range(retries):
            try:
                # 동시다발적 요청을 흩뿌리기 위해 0.1~0.5초 사이로 랜덤하게 쉬고 출발
                time.sleep(random.uniform(0.1, 0.5))
                ex = yf.Ticker(ticker).info.get('exchange', '').upper()
                
                if ex:  # 성공적으로 가져왔으면 즉시 반환
                    return ticker, ex, None
                    
            except Exception as e:
                # 429 (Too Many Requests) 차단 에러 시 좀 더 길게 쉬었다가 재시도
                if "429" in str(e) or "Too Many Requests" in str(e):
                    time.sleep(2)
                
                # 마지막 시도까지 실패하면 에러 메시지 반환
                if attempt == retries - 1:
                    return ticker, None, str(e)
                    
        return ticker, None, "정보 없음"

    def handle(self, *args, **kwargs):
        # 1. 이미 완료된 872개를 제외한 나머지 빈 종목만 불러옵니다.
        stocks_to_fetch = StockMaster.objects.filter(
            Q(exchange__isnull=True) | Q(exchange=''), market='US'
        ).exclude(market='COIN').exclude(ticker__contains='-')

        total_count = stocks_to_fetch.count()
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ 빈 종목이 없습니다. 모두 완벽하게 업데이트되었습니다!"))
            return

        self.stdout.write(self.style.WARNING(f"🔍 남은 {total_count}개 종목 업데이트 재개 (안전 모드 가동)..."))

        chunk_size = 50
        processed_count = 0
        error_count = 0
        ticker_list = list(stocks_to_fetch.values_list('ticker', flat=True))

        for i in range(0, total_count, chunk_size):
            chunk_tickers = ticker_list[i:i + chunk_size]
            current_batch_updates = []
            
            chunk_objs = StockMaster.objects.filter(ticker__in=chunk_tickers)
            obj_dict = {obj.ticker: obj for obj in chunk_objs}

            # 2. 워커(일꾼) 수를 10개에서 5개로 줄여서 차단 확률 최소화
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.fetch_exchange, ticker): ticker for ticker in chunk_tickers}
                
                for future in as_completed(futures):
                    ticker, ex, error = future.result()
                    
                    # 에러가 나서 끝까지 못 가져온 경우 콘솔에 빨간색으로 살짝 표시
                    if error:
                        error_count += 1
                        # self.stdout.write(self.style.ERROR(f"[{ticker}] 실패: {error}"))
                        continue
                        
                    if not ex:
                        continue
                        
                    # 거래소 이름 정규화
                    if ex in ['NMS', 'NGM', 'NASDAQGS', 'NASDAQ']: new_ex = 'NASDAQ'
                    elif ex in ['NYQ', 'NYSE']: new_ex = 'NYSE'
                    elif ex in ['ASE', 'AMEX']: new_ex = 'AMEX'
                    elif ex in ['KSC', 'KOSPI']: new_ex = 'KOSPI'
                    elif ex in ['KOE', 'KOSDAQ']: new_ex = 'KOSDAQ'
                    else: new_ex = ex

                    if ticker in obj_dict:
                        stock_obj = obj_dict[ticker]
                        stock_obj.exchange = new_ex
                        current_batch_updates.append(stock_obj)

            # 3. DB에 일괄 저장
            if current_batch_updates:
                StockMaster.objects.bulk_update(current_batch_updates, ['exchange'])
                processed_count += len(current_batch_updates)

            progress_percent = min((i + chunk_size) / total_count * 100, 100)
            self.stdout.write(self.style.SUCCESS(
                f"🛡️ 안전 처리 중: [{min(i + chunk_size, total_count)}/{total_count}] ({progress_percent:.1f}%) ... (이번 턴 성공: {processed_count})"
            ))
            
            # 한 뭉치(50개) 끝날 때마다 야후 서버가 진정하도록 1.5초 크게 쉼
            time.sleep(1.5)

        self.stdout.write(self.style.SUCCESS(f"\n✨ 남은 작업 완료! (새로 채워진 종목: {processed_count}개 / 끝내 조회 실패한 종목: {error_count}개)"))