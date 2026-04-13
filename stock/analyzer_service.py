import pytz
from datetime import datetime
from django.utils import timezone
from .models import StockMaster, MyTrackedStock, StockAnalysisLatest, StockAnalysisHistory
from .utils import analyze_batch_signals # 기존 분석 함수

class MarketAnalyzerService:
    @staticmethod
    def get_target_markets():
        """현재 KST 시간 기준 분석할 시장 목록 반환"""
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        hour = now.hour
        is_weekend = now.weekday() >= 5  # 5: 토요일, 6: 일요일
        
        markets = []
        markets = ['COIN'] # 코인은 24시간 상시
        
        if not is_weekend:
            # 한국 시장: 09시 ~ 16시
            if 9 <= hour <= 16:
                markets.append('KR')
                
            # 미국 시장: 23시 ~ 07시 (서머타임 미고려 시 기준, 필요 시 조정 가능)
            if hour >= 22 or hour <= 7:
                markets.append('US')
        
        # markets.append('US')
        # markets.append('KR')
        return markets, now.date()

    @classmethod
    def run_analysis(cls):
        """전체 분석 프로세스 실행"""
        target_markets, today_date = cls.get_target_markets()
        print(f"🕒 분석 시작 (KST): {datetime.now()} | 대상 시장: {target_markets}")

        # 1. 대상 티커 수집 (관심종목 + 지수 종목)
        my_list = set(MyTrackedStock.objects.filter(
            stock__market__in=target_markets
        ).values_list('stock__ticker', flat=True))
        
        index_list = set(StockMaster.objects.filter(
            market__in=target_markets,
            index_type__isnull=False  # 🚀 여기가 필터링의 핵심입니다!
        ).values_list('ticker', flat=True))

        all_tickers = list(my_list | index_list)
        
        if not all_tickers:
            print("데이터 없음: 현재 분석할 종목이 없습니다.")
            return

        # 2. 배치 분석 (50개 단위)
        batch_size = 50
        for i in range(0, len(all_tickers), batch_size):
            batch = all_tickers[i:i + batch_size]
            results = analyze_batch_signals(batch)

            for ticker, data in results.items():
                stock = StockMaster.objects.get(ticker=ticker)
                
                # 오류 원인 해결: 모델에 정의된 필드만 추출
                analysis_defaults = {
                    't_signal': data.get('t_signal', 'gray'),
                    'n_signal': data.get('n_signal', 'gray'),
                    'c_signal': data.get('c_signal', 'gray'),
                    'p_name': data.get('p_name', '대기중'),
                    'p_code': data.get('p_code', '대기중'),
                    'up_days': data.get('up_days', 0),
                    # 🚀 새로 추가한 컬럼 매핑
                    'signal_code': data.get('signal_code', 'd01'),
                }
                
                # [트랙 1] 최신 결과 (즉시 반영)
                StockAnalysisLatest.objects.update_or_create(
                    stock=stock, 
                    defaults=analysis_defaults
                )
                
                # [트랙 2] 히스토리 (일단위 기록)
                StockAnalysisHistory.objects.update_or_create(
                    stock=stock, 
                    date=today_date, 
                    defaults=analysis_defaults
                )
                
                # # [트랙 1] 최신 결과 (즉시 반영)
                # StockAnalysisLatest.objects.update_or_create(
                #     stock=stock, defaults=data
                # )
                
                # # [트랙 2] 히스토리 (일단위 기록)
                # StockAnalysisHistory.objects.update_or_create(
                #     stock=stock, date=today_date, defaults=data
                # )
        
        print(f"✅ 총 {len(all_tickers)}개 종목 분석 및 저장 완료")