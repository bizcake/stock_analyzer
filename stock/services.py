import logging
import pytz
from datetime import datetime
from django.utils import timezone
from .models import StockMaster, MyTrackedStock, StockAnalysisLatest, StockAnalysisHistory
from .utils import analyze_batch_signals

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

            # 내 관심 종목 중 해당 마켓인 것들만 수집
            query = MyTrackedStock.objects.select_related('stock').filter(stock__market__in=target_markets)
            target_tickers = [item.stock.ticker for item in query]

        if not target_tickers:
            logger.warning("분석할 티커가 없습니다.")
            return 0

        # 2. 배치 분석 호출
        batch_results = analyze_batch_signals(target_tickers)
        if not batch_results:
            logger.error("분석 결과가 비어있습니다.")
            return 0

        processed_count = 0

        # 3. DB 저장 (Latest 및 History)
        for ticker, res in batch_results.items():
            try:
                stock = StockMaster.objects.get(ticker=ticker)
                
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
            except StockMaster.DoesNotExist:
                logger.error(f"티커 {ticker}를 찾을 수 없습니다.")
            except Exception as e:
                logger.error(f"[{ticker}] 저장 중 에러: {e}")

        return processed_count
