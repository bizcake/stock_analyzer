# [앱이름]/management/commands/cron_analyze.py
import pytz
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from stock.models import MyTrackedStock, StockMaster, StockAnalysisLatest, StockAnalysisHistory
from stock.utils import analyze_batch_signals

class Command(BaseCommand):
    def handle(self, *args, **options):
        kst = pytz.timezone('Asia/Seoul')
        now = timezone.now().astimezone(kst)
        today_date = now.date()

        # 1. 타겟 시장 설정 (시간대별 최적화)
        target_markets = ['COIN']
        if 9 <= now.hour <= 16: target_markets.append('KR')
        if now.hour >= 23 or now.hour <= 7: target_markets.append('US')

        # 2. 대상 티커 수집 및 중복 제거
        my_tickers = set(MyTrackedStock.objects.filter(stock__market__in=target_markets).values_list('stock__ticker', flat=True))
        index_tickers = set(StockMaster.objects.filter(market__in=target_markets, is_index_member=True).values_list('ticker', flat=True))
        all_tickers = list(my_tickers | index_tickers)
        
        if not all_tickers: return

        # 3. 배치 분석 및 투 트랙 저장
        batch_size = 50
        for i in range(0, len(all_tickers), batch_size):
            batch = all_tickers[i:i + batch_size]
            results = analyze_batch_signals(batch)

            for ticker, data in results.items():
                stock = StockMaster.objects.get(ticker=ticker)
                
                # [트랙 1] 최신 테이블: 무조건 덮어쓰기 (UI 즉각 반영)
                StockAnalysisLatest.objects.update_or_create(
                    stock=stock,
                    defaults=data
                )
                
                # [트랙 2] 히스토리 테이블: 오늘 날짜로 덮어쓰거나 새로 만들기
                # 장중에는 오늘 날짜의 데이터가 계속 최신화되다가, 
                # 다음 날이 되면 새로운 날짜의 데이터가 자동으로 INSERT 됩니다.
                StockAnalysisHistory.objects.update_or_create(
                    stock=stock,
                    date=today_date,
                    defaults=data
                )

        # 4. 오래된 히스토리 정리 (6개월 전)
        six_months_ago = today_date - timedelta(days=180)
        StockAnalysisHistory.objects.filter(date__lt=six_months_ago).delete()