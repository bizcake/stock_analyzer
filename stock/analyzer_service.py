import pytz
from datetime import datetime, timedelta
from django.utils import timezone
from .models import StockMaster, MyTrackedStock, StockAnalysisLatest, StockAnalysisHistory
from .utils import (
    get_final_signal_with_code, analyze_candle_pattern, 
    calc_hma, calc_wavetrend, calc_macd
)
import os
import yfinance as yf
import pandas as pd
import numpy as np

# 1. 환경 분리: 구글 클라우드 환경인지 확인
IS_CLOUD_RUN = os.environ.get('K_SERVICE') is not None

def analyze_batch_signals(tickers_list):
    """야후 데이터 일괄 다운로드 + 기술적 지표 분석 + 정밀 타점 시그널 반환"""
    if not tickers_list:
        return {}

    print(f"📊 분석 시작... 대상 종목 수: {len(tickers_list)}개")
    name_map = dict(StockMaster.objects.filter(ticker__in=tickers_list).values_list('ticker', 'name_kr'))
    
    df_all = yf.download(tickers_list, period="1y", progress=False)
    if df_all.empty:
        return {}

    results = {}
    for ticker in tickers_list:
        try:
            df = df_all.copy()
            if isinstance(df.columns, pd.MultiIndex):
                if ticker in df.columns.get_level_values(0): df = df[ticker].copy()
                elif ticker in df.columns.get_level_values(1): df = df.xs(ticker, axis=1, level=1).copy()
                else: continue
            
            df.dropna(inplace=True)
            if df.empty or len(df) < 120: continue

            close_p = float(df['Close'].iloc[-1])

            # 연속 상승 일수
            diff = df['Close'].diff().dropna()
            up_days = 0
            for val in diff.iloc[::-1]:
                if val > 0: up_days += 1
                else: break

            # T 신호등 (Hull MA & WaveTrend)
            df['HMA'] = calc_hma(df['Close'], 14)
            wt1, wt2 = calc_wavetrend(df)
            hma_up = df['HMA'].iloc[-1] > df['HMA'].iloc[-2]
            wt_up = (wt1.iloc[-1] > wt2.iloc[-1]) and (wt1.iloc[-1] > wt1.iloc[-2])
            t_signal = 'green' if hma_up and wt_up else ('red' if not hma_up and not wt_up else 'orange')

            # N 신호등 (SMA20, MACD, OBV)
            df['SMA_20'] = df['Close'].rolling(20).mean()
            macd, macd_sig = calc_macd(df['Close'])
            df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
            df['OBV_SMA20'] = df['OBV'].rolling(20).mean()
            
            price_up = close_p > df['SMA_20'].iloc[-1]
            macd_up = macd.iloc[-1] > macd_sig.iloc[-1]
            obv_up = (df['OBV_SMA20'].iloc[-1] > df['OBV_SMA20'].iloc[-5]) and (df['OBV'].iloc[-1] > df['OBV'].iloc[-20])
            n_score = sum([price_up, macd_up, obv_up])
            n_signal = 'green' if n_score == 3 else ('red' if n_score == 0 else 'orange')

            # ATR (Average True Range) 14일 계산
            tr1 = df['High'] - df['Low']
            tr2 = (df['High'] - df['Close'].shift(1)).abs()
            tr3 = (df['Low'] - df['Close'].shift(1)).abs()
            atr_14 = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1]

            # C 신호등 및 캔들 패턴
            c_signal, p_code, p_name = analyze_candle_pattern(
                df['Open'].iloc[-1], df['High'].iloc[-1], df['Low'].iloc[-1], close_p, df['Close'].iloc[-2], atr_14
            )

            # 정밀 타점 (RSI, 스토캐스틱, 120일선)
            s5_s = df['Close'].rolling(5).mean()
            s5, s5_prev = s5_s.iloc[-1], s5_s.iloc[-2]
            s20 = df['SMA_20'].iloc[-1]
            s120 = df['Close'].rolling(120).mean().iloc[-1]

            gain = (diff.where(diff > 0, 0)).rolling(14).mean()
            loss = (-diff.where(diff < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan)).iloc[-1]))

            hist_up = (macd - macd_sig).iloc[-1] > (macd - macd_sig).iloc[-2]
            macd_cross = macd.iloc[-1] > macd_sig.iloc[-1]
            obv_confirmed = df['OBV'].iloc[-1] > df['OBV'].ewm(span=10).mean().iloc[-1]

            low_14, high_14 = df['Low'].rolling(14).min(), df['High'].rolling(14).max()
            stoch_k = (100 * (df['Close'] - low_14) / (high_14 - low_14)).rolling(3).mean()
            stoch_d = stoch_k.rolling(3).mean()
            stoch_cross = (stoch_k.iloc[-1] > stoch_d.iloc[-1]) and (stoch_k.iloc[-2] <= stoch_d.iloc[-2])

            final_text, final_code = get_final_signal_with_code(
                rsi, hist_up, macd_cross, obv_confirmed, close_p,
                s5, s5_prev, s20, s120, stoch_k.iloc[-1], stoch_d.iloc[-1], stoch_cross
            )

            results[ticker] = {
                'ticker': ticker,
                'name_kr': name_map.get(ticker, ticker),
                't_signal': t_signal,
                'n_signal': n_signal,
                'c_signal': c_signal,
                'p_name': p_name,           
                'p_code': p_code,           
                'final_signal': final_text, 
                'signal_code': final_code,  
                'up_days': up_days
            }
        except Exception as e:
            print(f"[{ticker}] 분석 중 에러: {e}")
            
    return results

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
        
        if IS_CLOUD_RUN == False:
            markets = []
            # markets.append('US')
            markets.append('KR')
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
        

        if IS_CLOUD_RUN:
            index_list = set(StockMaster.objects.filter(
                market__in=target_markets,
                index_type__isnull=False  # 🚀 여기가 필터링의 핵심입니다!
            ).values_list('ticker', flat=True))
        else:
            index_list = set([])

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
                
                # 4. 오래된 히스토리 정리 (6개월 전)
                six_months_ago = today_date - timedelta(days=180)
                StockAnalysisHistory.objects.filter(date__lt=six_months_ago).delete()
        
        print(f"✅ 총 {len(all_tickers)}개 종목 분석 및 저장 완료")