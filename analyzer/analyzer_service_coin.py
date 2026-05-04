import pytz
from analyzer.error_logger import trace_exceptions
from stock.models import StockMaster, CoinAnalysisLatest
from .indicators import (
    calc_wavetrend, calc_macd, calc_rsi, calc_supertrend,
    calc_adx, calc_obv, calc_squeeze,
)
import math
import time
import requests
import pandas as pd
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

BINGX_BASE = "https://open-api.bingx.com"

@trace_exceptions
def _sanitize_and_log_nan(ticker: str, interval: str, data: dict) -> dict:
    """딕셔너리 내의 NaN 값을 찾아 로그를 찍고, DB 적재 가능한 None으로 치환"""
    clean_data = {}
    nan_fields = []

    for k, v in data.items():
        # Decimal 객체의 NaN 체크
        if isinstance(v, Decimal) and v.is_nan():
            nan_fields.append(k)
            clean_data[k] = None
        # Float 또는 Pandas NA 체크
        elif pd.isna(v) or (isinstance(v, float) and math.isnan(v)):
            nan_fields.append(k)
            clean_data[k] = None
        else:
            clean_data[k] = v

    if nan_fields:
        print(f"⚠️ [{ticker} - {interval}] NaN 감지 필드 (None으로 치환됨): {nan_fields}")

    return clean_data

def fetch_bingx_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """BingX Public API 캔들 데이터 조회 (API Key 불필요)"""
    url = f"{BINGX_BASE}/openApi/swap/v3/quote/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get('code') != 0:
            print(f"[{symbol}] BingX 오류: {data.get('msg')}")
            return pd.DataFrame()
            
        rows = data['data']
        # BingX API 응답은 딕셔너리 형태이므로 컬럼 매핑 수정
        df = pd.DataFrame(rows)

        # 컬럼명 통일 및 타입 변환
        rename_map = {
            'time':   'timestamp',
            'open':   'Open',
            'high':   'High',
            'low':    'Low',
            'close':  'Close',
            'volume': 'Volume'
        }
        df.rename(columns=rename_map, inplace=True)

        # 시간 변환 및 데이터 타입 강제 지정
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
    except Exception as e:
        print(f"[{symbol}] API 호출 실패: {e}")
        return pd.DataFrame()

@trace_exceptions
def _analyze_coin_df(df: pd.DataFrame) -> dict | None:
    """BingX DataFrame 1h/4h 단일 분석 로직 (롱/숏 양방향 타점 및 과열 필터 적용)"""
    try:
        close = df['Close']
        close_p = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) > 1 else close_p

        # ── 지표 계산 ──
        wt1, wt2           = calc_wavetrend(df)
        macd, macd_sig     = calc_macd(close)
        macd_hist          = macd - macd_sig
        rsi                = float(calc_rsi(close).iloc[-1])
        adx                = calc_adx(df)
        
        st_dir, st_val     = calc_supertrend(df)
        df_prev            = df.iloc[:-1].copy()
        st_dir_prev, _     = calc_supertrend(df_prev)
        
        obv, obv_confirmed = calc_obv(df)
        sq                 = calc_squeeze(df, wt1, wt2)

        # ── 기초 변수 및 상태 계산 ──
        wt1_curr, wt2_curr = float(wt1.iloc[-1]), float(wt2.iloc[-1])
        wt1_prev, wt2_prev = float(wt1.iloc[-2]), float(wt2.iloc[-2])
        
        wt_cross_up   = (wt1_curr > wt2_curr) and (wt1_prev <= wt2_prev)
        wt_cross_down = (wt1_curr < wt2_curr) and (wt1_prev >= wt2_prev)
        wt_oversold   = wt1_curr < -60
        wt_overbought = wt1_curr > 60
        wt_rising     = wt1_curr > wt1_prev

        # 20일선, 등락률, 이격도 산출
        change_rate = ((close_p - prev_close) / prev_close) * 100
        sma20       = close.rolling(20).mean()
        sma20_val   = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else close_p
        deviation   = ((close_p - sma20_val) / sma20_val) * 100 if sma20_val > 0 else 0

        # BB 밴드폭 산출
        bb_std = close.rolling(20).std()
        bb_width_series = pd.Series(0.0, index=close.index)
        valid_idx = sma20 > 0
        bb_width_series[valid_idx] = ((sma20[valid_idx] + 2*bb_std[valid_idx]) - (sma20[valid_idx] - 2*bb_std[valid_idx])) / sma20[valid_idx]
        
        bb_mean = bb_width_series.rolling(20).mean().iloc[-1]
        
        # 추세 전환 확인
        st_just_turned_up   = (st_dir == 1) and (st_dir_prev == -1)
        st_just_turned_down = (st_dir == -1) and (st_dir_prev == 1)
        
        # BB 5봉 연속 수축 검증 (신뢰도 상향)
        is_bb_valid = not pd.isna(bb_mean)
        bb_was_narrow = (bb_width_series.iloc[-5:].min() < bb_mean * 0.7) if is_bb_valid else False
        bb_already_expanded = (bb_width_series.iloc[-1] > bb_mean * 1.3) if is_bb_valid else False

        sr = sq.get('squeeze_released', False)
        vs = sq.get('vol_surge', False)
        is_sq = sq.get('is_squeeze', False)

        # ── 롱/숏 추격 금지(과열) 필터 ──
        # 코인 1시간/4시간봉 기준: 한 캔들 등락률 5% 초과 or 이격도 10% 초과 시 과열로 간주
        is_chasing_long  = (change_rate > 5) or bb_already_expanded or (deviation > 10)
        is_chasing_short = (change_rate < -5) or bb_already_expanded or (deviation < -10)
        is_pullback      = abs(deviation) < 5  # 20일선 근처의 안전한 눌림목

        # ── 🚨 1. 추격 금지 최우선 필터 ──
        if (st_just_turned_up or wt_cross_up) and is_chasing_long and not is_pullback:
            sig = ("⚠️ 롱 추격 금지 (과열)", "b03", 4, f"이격도({deviation:.1f}%)/확장. 눌림목 대기")
        elif (st_just_turned_down or wt_cross_down) and is_chasing_short and not is_pullback:
            sig = ("⚠️ 숏 추격 금지 (낙폭 과대)", "c03", 4, f"이격도({deviation:.1f}%)/확장. 반등 대기")

        # ── 🟢 2. 롱(Long) 포지션 시그널 ──
        elif st_just_turned_up and bb_was_narrow and vs and wt_rising and obv_confirmed:
            sig = ("🚀 롱 진입 (응축 상방폭발)", "a00", 1, "ST상승+BB수축+수급. 롱 최적 타점")
        elif st_dir == 1 and wt_cross_up and wt_oversold and obv_confirmed and deviation < 10:
            sig = ("🔥 롱 진입 (눌림목 반등)", "a01", 2, "상승추세 내 과매도권 20일선 지지 롱")
        elif st_dir == 1 and wt_cross_up and not wt_overbought and deviation < 10:
            sig = ("✅ 롱 유지/진입 (추세 지속)", "a02", 3, "안전한 롱 추가 진입 구간")

        # ── 🔴 3. 숏(Short) 포지션 시그널 ──
        # 숏 타점은 OBV가 하락(not obv_confirmed)하거나 WT가 하락 중일 때 신뢰도 상승
        elif st_just_turned_down and bb_was_narrow and vs and not wt_rising:
            sig = ("💥 숏 진입 (응축 하방폭발)", "d00", 1, "ST하락+BB수축+수급이탈. 숏 최적 타점")
        elif st_dir == -1 and wt_cross_down and wt_overbought and deviation > -10:
            sig = ("🔥 숏 진입 (반등 후 재하락)", "d01", 2, "하락추세 내 과매수권 저항 숏")
        elif st_dir == -1 and wt_cross_down and not wt_oversold and deviation > -10:
            sig = ("✅ 숏 유지/진입 (하락 지속)", "d02", 3, "안전한 숏 추가 진입 구간")

        # ── 🔄 4. 방향 탐색 및 청산(익절) 로직 ──
        elif bb_was_narrow and wt_rising and not is_sq:
            sig = ("↔️ 롱 방향 탐색 (ST 전환 대기)", "a03", 3, "상방 응축 해제 확인. ST 전환 대기")
        elif bb_was_narrow and not wt_rising and not is_sq:
            sig = ("↔️ 숏 방향 탐색 (ST 전환 대기)", "d03", 3, "하방 응축 해제 확인. ST 전환 대기")
        elif st_dir == 1 and wt_overbought and wt_cross_down:
            sig = ("⚠️ 롱 익절 주의 (고점 시그널)", "b03", 4, "과매수 WT 꺾임. 롱 포지션 익절 고려")
        elif st_dir == -1 and wt_oversold and wt_cross_up:
            sig = ("⚠️ 숏 익절 주의 (단기 바닥)", "a04", 5, "과매도 WT 꺾임. 숏 포지션 익절 고려")
        else:
            sig = ("↔️ 관망 (방향성 부재)", "c02", 0, "진입 자제 및 추세 대기")

        # 거래량 배수 산출
        vol_curr  = float(df['Volume'].iloc[-1])
        vol_ma20  = sq.get('vol_ma20', 0)
        vol_ratio = round(vol_curr / vol_ma20, 2) if vol_ma20 > 0 else 0

        return {
            'close_price':          Decimal(str(round(close_p, 8))),
            'volume':               vol_curr,
            'vol_ratio':            vol_ratio,
            'change_rate':          round(change_rate, 2),
            'signal':               sig[0],
            'signal_code_id':       sig[1],
            'priority':             sig[2],
            'action':               sig[3],
            'supertrend_direction': st_dir,
            'wt1':                  round(wt1_curr, 4),
            'wt2':                  round(wt2_curr, 4),
            'wt_cross_up':          wt_cross_up,
            'wt_cross_down':        wt_cross_down,
            'wt_oversold':          wt_oversold,
            'wt_overbought':        wt_overbought,
            'wt_momentum':          round(wt1_curr - wt1_prev, 4),
            'is_squeeze':           is_sq,
            'squeeze_released':     sr,
            'rsi':                  round(rsi, 2),
            'macd':                 round(float(macd.iloc[-1]), 4),
            'macd_hist':            round(float(macd_hist.iloc[-1]), 4),
            'adx':                  round(adx, 2) if not pd.isna(adx) else 0,
            'obv_confirmed':        obv_confirmed,
        }

    except Exception as e:
        print(f"  [분석 오류]: {e}")
        return None
# def _analyze_coin_df(df: pd.DataFrame) -> dict | None:
#     """BingX DataFrame 1h/4h 단일 분석 로직"""
#     try:
#         close = df['Close']
#         close_p = float(close.iloc[-1])

#         # ── 지표 계산 ──
#         wt1, wt2           = calc_wavetrend(df)
#         macd, macd_sig     = calc_macd(close)
#         macd_hist          = macd - macd_sig
#         rsi                = float(calc_rsi(close).iloc[-1])
#         adx                = calc_adx(df)
        
#         st_dir, st_val     = calc_supertrend(df)
#         df_prev            = df.iloc[:-1].copy()
#         st_dir_prev, _     = calc_supertrend(df_prev)
        
#         obv, obv_confirmed = calc_obv(df)
#         sq                 = calc_squeeze(df, wt1, wt2)

#         # ── 시그널 판별 로직 ──
#         wt1_curr, wt2_curr = float(wt1.iloc[-1]), float(wt2.iloc[-1])
#         wt1_prev, wt2_prev = float(wt1.iloc[-2]), float(wt2.iloc[-2])
        
#         wt_cross_up   = (wt1_curr > wt2_curr) and (wt1_prev <= wt2_prev)
#         wt_cross_down = (wt1_curr < wt2_curr) and (wt1_prev >= wt2_prev)
#         wt_oversold   = wt1_curr < -60
#         wt_overbought = wt1_curr > 60
#         wt_rising     = wt1_curr > wt1_prev

#         # BB 밴드폭 산출
#         bb_mid = close.rolling(20).mean()
#         bb_std = close.rolling(20).std()
        
#         bb_width_series = pd.Series(0.0, index=close.index)
#         valid_idx = bb_mid > 0
#         bb_width_series[valid_idx] = ((bb_mid[valid_idx] + 2*bb_std[valid_idx]) - (bb_mid[valid_idx] - 2*bb_std[valid_idx])) / bb_mid[valid_idx]
        
#         bb_mean = bb_width_series.rolling(20).mean().iloc[-1]
#         st_just_turned_up = (st_dir == 1) and (st_dir_prev == -1)
        
#         is_bb_valid = not pd.isna(bb_mean)
#         bb_was_narrow = (bb_width_series.iloc[-3:].min() < bb_mean * 0.7) if is_bb_valid else False
#         bb_already_expanded = (bb_width_series.iloc[-1] > bb_mean * 1.3) if is_bb_valid else False

#         sr = sq['squeeze_released']
#         vs = sq['vol_surge']

#         if st_just_turned_up and bb_already_expanded:
#             sig = ("⚠️ 추격 금지 (폭발 후 전환)", "b03", 4, "BB 이미 확대 완료. 눌림목 대기")
#         elif st_just_turned_up and bb_was_narrow and vs and wt_rising and obv_confirmed:
#             sig = ("🚀 응축 폭발 (즉시 진입)", "a00", 1, "최적 타점")
#         elif st_just_turned_up and bb_was_narrow:
#             sig = ("🔥 응축 돌파 (ST 전환 확인)", "a01", 2, "ST 상향 전환")
#         elif bb_was_narrow and wt_rising and not sq['is_squeeze']:
#             sig = ("↔️ 응축 해제 대기 (ST 전환 확인 전)", "a03", 3, "ST 전환 대기")
#         elif sr and wt_cross_up and st_dir == 1:
#             sig = ("🚀 적극 매수 (응축 돌파)", "a00", 1, "상승추세 응축 해제")
#         elif st_dir == 1 and wt_cross_up and wt_oversold and obv_confirmed:
#             sig = ("🔥 강력 매수 (눌림목)", "a01", 2, "핵심 매수 타점")
#         elif st_dir == 1 and wt_cross_up and not wt_overbought:
#             sig = ("✅ 매수 (추세 지속)", "a02", 3, "안전 진입 구간")
#         elif st_dir == 1 and wt_overbought and wt_cross_down:
#             sig = ("⚠️ 고점 주의", "b03", 4, "WT 꺾임. 익절 고려")
#         elif st_dir == -1 and wt_cross_down:
#             sig = ("📉 매도 (하락 가속)", "b01", 5, "보유 청산 고려")
#         else:
#             sig = ("↔️ 방향 탐색 중", "c02", 0, "대기")

#         vol_curr  = float(df['Volume'].iloc[-1])
#         vol_ma20  = sq['vol_ma20']
#         vol_ratio = round(vol_curr / vol_ma20, 2) if vol_ma20 > 0 else 0
        
#         prev_close  = float(close.iloc[-2])
#         change_rate = round((close_p - prev_close) / prev_close * 100, 2) if prev_close else 0

#         return {
#             'close_price':          Decimal(str(round(close_p, 8))),
#             'volume':               vol_curr,
#             'vol_ratio':            vol_ratio,
#             'change_rate':          change_rate,
#             'signal':               sig[0],
#             'signal_code_id':       sig[1],
#             'priority':             sig[2],
#             'action':               sig[3],
#             'supertrend_direction': st_dir,
#             'wt1':                  round(wt1_curr, 4),
#             'wt2':                  round(wt2_curr, 4),
#             'wt_cross_up':          wt_cross_up,
#             'wt_cross_down':        wt_cross_down,
#             'wt_oversold':          wt_oversold,
#             'wt_overbought':        wt_overbought,
#             'wt_momentum':          round(wt1_curr - wt1_prev, 4),
#             'is_squeeze':           sq['is_squeeze'],
#             'squeeze_released':     sq['squeeze_released'],
#             'rsi':                  round(rsi, 2),
#             'macd':                 round(float(macd.iloc[-1]), 4),
#             'macd_hist':            round(float(macd_hist.iloc[-1]), 4),
#             'adx':                  round(adx, 2) if not pd.isna(adx) else 0,
#             'obv_confirmed':        obv_confirmed,
#         }

#     except Exception as e:
#         print(f"  [분석 오류]: {e}")
#         return None
    
class MarketAnalyzerService:

    @classmethod
    def run_analysis(cls):
        """전체 분석 프로세스 실행"""
        target_markets = ['COIN'] 
        """BingX 1h/4h 데이터 수집 및 DB 적재 프로세스"""
        coins = list(StockMaster.objects.filter(market='COIN').values_list('ticker', flat=True))
        
        for ticker in coins:
            symbol = ticker.replace('-USD', '-USDT')
            
            for interval in ['1h', '4h']:
                df = fetch_bingx_klines(symbol, interval, limit=200)
                
                if df.empty or len(df) < 150:
                    print(f"[{ticker}] {interval} 데이터 불충분")
                    continue
                    
                raw_result = _analyze_coin_df(df)
                if not raw_result:
                    continue
                
                # ✅ 추가: NaN 값 검사, 로그 출력 및 None 치환
                result = _sanitize_and_log_nan(ticker, interval, raw_result)
                
                # 필수 필드(종가 등)가 None이 되어버렸다면 저장을 스킵
                if result['close_price'] is None:
                    print(f"❌ [{ticker} - {interval}] 종가(close_price)가 NaN입니다. 저장을 스킵합니다.")
                    continue
                
                try:
                    with transaction.atomic():
                        CoinAnalysisLatest.objects.update_or_create(
                            stock_id=ticker,
                            interval=interval,
                            defaults={
                                'analyzed_at':          timezone.now(),
                                'close_price':          result['close_price'],
                                'volume':               result['volume'],
                                'vol_ratio':            result['vol_ratio'],
                                'change_rate':          result['change_rate'],
                                'signal_code_id':       result['signal_code_id'],
                                'signal':               result['signal'],
                                'priority':             result['priority'],
                                'action':               result['action'],
                                'supertrend_direction': result['supertrend_direction'],
                                'wt1':                  result['wt1'],
                                'wt2':                  result['wt2'],
                                'wt_cross_up':          result['wt_cross_up'],
                                'wt_cross_down':        result['wt_cross_down'],
                                'wt_oversold':          result['wt_oversold'],
                                'wt_overbought':        result['wt_overbought'],
                                'wt_momentum':          result['wt_momentum'],
                                'is_squeeze':           result['is_squeeze'],
                                'squeeze_released':     result['squeeze_released'],
                                'rsi':                  result['rsi'],
                                'macd':                 result['macd'],
                                'macd_hist':            result['macd_hist'],
                                'adx':                  result['adx'],
                                'obv_confirmed':        result['obv_confirmed'],
                            }
                        )
                except Exception as e:
                    # ❌ 에러 발생 시 전체 payload 출력
                    print(f"[{ticker} - {interval}] DB 저장 에러: {e}")
                    print(f"  [상세 Payload]: {result}")
                    
            time.sleep(0.5)
        
