import logging
import pytz
from datetime import datetime, timedelta
from django.utils import timezone
from ..stock.models import StockMaster, MyTrackedStock, StockAnalysisLatest, StockAnalysisHistory
from ..stock.utils import analyze_batch_signals

logger = logging.getLogger(__name__)

class StockAnalyzerService:
    
    @classmethod
    def get_active_markets(cls):
        """현재 KST 시간 기준 분석할 시장 목록 및 기준 날짜 반환"""
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        hour = now.hour
        is_weekend = now.weekday() >= 5  # 5: 토요일, 6: 일요일
        
        markets = ['COIN']  # 코인은 24시간 상시
        
        if not is_weekend:
            # 한국 시장: 09시 ~ 16시
            if 9 <= hour <= 16:
                markets.append('KR')
                
            # 미국 시장: 22시 ~ 07시 (서머타임 미고려 기준)
            if hour >= 22 or hour <= 7:
                markets.append('US')
        
        return markets, now.date()

    @classmethod
    def run_analysis(cls, market=None, tickers=None):
        """
        주식 분석을 실행하고 결과를 DB에 저장하는 통합 서비스.
        :param market: 특정 마켓 ('KR', 'US', 'COIN') 필터링. 지정 안 되면 시간대별 자동 판단.
        :param tickers: 특정 티커 리스트 분석.
        :return: 분석된 종목 수
        """
        analysis_date = timezone.now().date()
        
        # 1. 분석 대상 마켓 및 날짜 결정
        if tickers:
            # 티커가 직접 들어오면 해당 티커만 분석
            target_tickers = tickers
        else:
            if market:
                # 마켓이 지정되면 해당 마켓만 분석
                target_markets = [market]
            else:
                # 마켓이 지정 안 되면 시간대별 자동 판단 (배치 모드)
                target_markets, auto_date = cls.get_active_markets()
                analysis_date = auto_date # KST 기준 날짜 사용
                logger.info(f"🕒 자동 마켓 감지: {target_markets} (기준일: {analysis_date})")

            # 내 관심 종목 및 지수 종목(is_index_member=True) 수집 (중복 제거)
            my_tickers = set(MyTrackedStock.objects.filter(stock__market__in=target_markets).values_list('stock__ticker', flat=True))
            index_tickers = set(StockMaster.objects.filter(market__in=target_markets, is_exchange=True).values_list('ticker', flat=True))
            target_tickers = list(my_tickers | index_tickers)

        if not target_tickers:
            logger.warning("분석할 티커가 없습니다.")
            return 0

        processed_count = 0
        batch_size = 50

        # 2. 배치 분석 및 DB 저장
        for i in range(0, len(target_tickers), batch_size):
            batch = target_tickers[i:i + batch_size]
            batch_results = analyze_batch_signals(batch)
            
            if not batch_results:
                logger.warning(f"일부 배치 분석 결과가 비어있습니다. (배치: {batch})")
                continue

            # 3. DB 저장 (Latest 및 History)
            for ticker, res in batch_results.items():
                # try:
                stock = StockMaster.objects.get(ticker=ticker)
                # except StockMaster.DoesNotExist:
                #     logger.error(f"티커 {ticker}를 찾을 수 없습니다.")
                # except Exception as e:
                #     logger.error(f"[{ticker}] 저장 중 에러: {e}")
                
                # Latest 업데이트
                StockAnalysisLatest.objects.update_or_create(
                    stock=stock,
                    defaults={
                        't_signal': res['t_signal'],
                        'n_signal': res['n_signal'],
                        'c_signal': res['c_signal'],
                        'p_code': res['p_code'],
                        'p_name': res['p_name'],
                        'up_days': res['up_days'],
                        'signal_code': res['signal_code'],
                    }
                )

                # History 기록 (시간대 로직에서 계산된 기준 날짜 사용)
                StockAnalysisHistory.objects.update_or_create(
                    stock=stock,
                    date=analysis_date,
                    defaults={
                        't_signal': res['t_signal'],
                        'n_signal': res['n_signal'],
                        'c_signal': res['c_signal'],
                        'p_code': res['p_code'],
                        'p_name': res['p_name'],
                        'up_days': res['up_days'],
                        'signal_code': res['signal_code'],
                    }
                )
                processed_count += 1

        # 4. 오래된 히스토리 정리 (6개월 전 데이터 삭제)
        if not tickers:  # 수동 단건 분석이 아닐 때만 실행
            six_months_ago = analysis_date - timedelta(days=180)
            StockAnalysisHistory.objects.filter(date__lt=six_months_ago).delete()

        return processed_count
