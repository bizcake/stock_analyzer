from os import close

import numpy as np
import pandas as pd

def calc_wma(series, period):
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calc_hma(series, period=14):
    half_length = int(period / 2)
    sqrt_length = int(np.sqrt(period))
    wmaf = calc_wma(series, half_length)
    wmas = calc_wma(series, period)
    return calc_wma(wmaf * 2 - wmas, sqrt_length)

def calc_wavetrend(df, n1=10, n2=21):
    ap = (df['High'] + df['Low'] + df['Close']) / 3
    esa = ap.ewm(span=n1, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=n1, adjust=False).mean()
    ci = (ap - esa) / (0.015 * d)
    wt1 = ci.ewm(span=n2, adjust=False).mean()
    wt2 = wt1.rolling(window=4).mean()
    return wt1, wt2

def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    return macd, macd_signal

def calc_rsi(close, period=14):
    """Wilder's Smoothing RSI — float 반환"""
    diff = close.diff()
    gain = diff.where(diff > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-diff.where(diff < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rsi  = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    return rsi

def calc_supertrend(df, period=10, multiplier=3.0):
    """트레이딩뷰와 100% 일치하는 SuperTrend 계산 함수 (RMA 방식 및 hl2 적용)"""
    
    # 1. 기준가 (hl2) 산출
    hl2 = (df['High'] + df['Low']) / 2
    
    # 2. True Range (TR) 산출
    df['tr0'] = abs(df['High'] - df['Low'])
    df['tr1'] = abs(df['High'] - df['Close'].shift(1))
    df['tr2'] = abs(df['Low'] - df['Close'].shift(1))
    tr = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    
    # 3. ATR 산출 (⭐️ 트레이딩뷰 방식인 RMA 사용: ewm alpha=1/period)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    
    # 4. 기본 상단/하단 밴드 계산
    basic_upperband = hl2 + (multiplier * atr)
    basic_lowerband = hl2 - (multiplier * atr)
    
    # 5. 최종 밴드 및 추세 방향 계산
    final_upperband = np.zeros(len(df))
    final_lowerband = np.zeros(len(df))
    trend = np.zeros(len(df))
    
    for i in range(len(df)):
        if i == 0:
            final_upperband[i] = basic_upperband.iloc[i]
            final_lowerband[i] = basic_lowerband.iloc[i]
            trend[i] = 1
            continue
            
        # Upper Band 로직
        if basic_upperband.iloc[i] < final_upperband[i-1] or df['Close'].iloc[i-1] > final_upperband[i-1]:
            final_upperband[i] = basic_upperband.iloc[i]
        else:
            final_upperband[i] = final_upperband[i-1]
            
        # Lower Band 로직
        if basic_lowerband.iloc[i] > final_lowerband[i-1] or df['Close'].iloc[i-1] < final_lowerband[i-1]:
            final_lowerband[i] = basic_lowerband.iloc[i]
        else:
            final_lowerband[i] = final_lowerband[i-1]
            
        # Trend 방향 결정
        if df['Close'].iloc[i] > final_upperband[i-1]:
            trend[i] = 1
        elif df['Close'].iloc[i] < final_lowerband[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]
            
    # 호출부(`_analyze_one` 등)의 구조에 맞춰 기존 반환 형식 유지
    # (예: 이전 코드에서 st_dir, st_dir_prev, st_val 구조로 쓰고 있다면 그에 맞게 리턴)
    trend_curr = int(trend[-1])
    trend_prev = int(trend[-2]) if len(trend) > 1 else trend_curr
    st_value_curr = float(final_lowerband[-1] if trend_curr == 1 else final_upperband[-1])
    
    return trend_curr, trend_prev, st_value_curr

def calc_adx(df, period=14):
    """ADX 추세 강도 — float 반환"""
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    plus_dm  = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm  = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr      = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr
    dx       = 100 * (plus_di - minus_di).abs() / \
               (plus_di + minus_di).replace(0, np.nan)
    adx      = dx.ewm(alpha=1/period, adjust=False).mean()
    return float(adx.iloc[-1])

def calc_mfi(df, period=14):
    """MFI 자금흐름 — float 반환"""
    tp       = (df['High'] + df['Low'] + df['Close']) / 3
    mf       = tp * df['Volume']
    pos_flow = mf.where(tp > tp.shift(1), 0).rolling(period).sum()
    neg_flow = mf.where(tp < tp.shift(1), 0).rolling(period).sum()
    mfi      = 100 - (100 / (1 + pos_flow / neg_flow.replace(0, np.nan)))
    return float(mfi.iloc[-1])

def calc_obv(df):
    """OBV + EMA10/20 수급 확인 — bool 반환"""
    obv      = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    obv_e10  = obv.ewm(span=10).mean()
    obv_e20  = obv.ewm(span=20).mean()
    confirmed = bool(
        obv.iloc[-1] > obv_e10.iloc[-1] and
        obv.iloc[-1] > obv_e20.iloc[-1]
    )
    return obv, confirmed

def calc_atr(df, period=14):
    """ATR — float 반환"""
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low']  - df['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def calc_squeeze(df, wt1, wt2):
    """
    응축(Squeeze) 감지
    return: dict
    """
    close    = df['Close']
    volume   = df['Volume']

    bb_mid   = close.rolling(20).mean()
    bb_std   = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - close.shift()).abs(),
        (df['Low']  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr      = tr.rolling(20).mean()
    kc_upper = bb_mid + 1.5 * atr
    kc_lower = bb_mid - 1.5 * atr

    is_squeeze  = bool(
        bb_upper.iloc[-1] < kc_upper.iloc[-1] and
        bb_lower.iloc[-1] > kc_lower.iloc[-1]
    )
    was_squeeze = bool(
        bb_upper.iloc[-2] < kc_upper.iloc[-2] and
        bb_lower.iloc[-2] > kc_lower.iloc[-2]
    )

    vol_ma20     = float(volume.rolling(20).mean().iloc[-1])
    vol_curr     = float(volume.iloc[-1])
    vol_surge    = vol_curr > vol_ma20 * 1.5
    wt_gap_curr  = abs(float(wt1.iloc[-1]) - float(wt2.iloc[-1]))
    wt_gap_prev  = abs(float(wt1.iloc[-3]) - float(wt2.iloc[-3]))

    return {
        'is_squeeze':       is_squeeze,
        'squeeze_released': was_squeeze and not is_squeeze,
        'wt_converging':    wt_gap_curr < wt_gap_prev * 0.7,
        'vol_surge':        vol_surge,
        'vol_ma20':         vol_ma20,
        'vol_curr':         vol_curr,
    }

def calc_candle_pattern(open_p, high_p, low_p, close_p, prev_close, atr=0):
    """캔들 패턴 분석 — (c_signal, p_code, p_name) 반환"""
    length = high_p - low_p
    if length == 0:
        return 'gray', 'p04', '도지/단봉'

    body         = abs(close_p - open_p)
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p
    gap_str      = ' (갭상승)' if open_p > prev_close * 1.01 \
              else (' (갭하락)' if open_p < prev_close * 0.99 else '')

    if body / length < 0.1:
        return 'gray', 'p04', f'도지{gap_str}'

    threshold = atr * 0.7 if atr > 0 else prev_close * 0.05

    if close_p > open_p:
        if lower_shadow > body * 2:
            return 'green',  'p01', f'망치형{gap_str}'
        elif upper_shadow > body * 2:
            return 'orange', 'p03', f'역망치형{gap_str}'
        is_long = body > threshold
        return ('green', 'p07', f'장대양봉{gap_str}') if is_long \
          else ('orange', 'p02', f'단봉(양){gap_str}')
    else:
        if upper_shadow > body * 2:
            return 'red',    'p06', f'유성형{gap_str}'
        elif lower_shadow > body * 2:
            return 'orange', 'p08', f'교수형{gap_str}'
        is_long = body > threshold
        return ('red', 'p09', f'장대음봉{gap_str}') if is_long \
          else ('orange', 'p05', f'단봉(음){gap_str}')
    
def _calc_market_state(df):
    """시그널 판정에 필요한 등락률, 이격도, BB 밴드폭 상태를 사전 연산"""
    close = df['Close']
    close_p = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) > 1 else close_p
    
    # 1. 당일 등락률
    change_rate = ((close_p - prev_close) / prev_close) * 100
    
    # 2. 20일선 및 이격도
    sma20 = close.rolling(20).mean()
    sma20_val = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else close_p
    deviation = ((close_p - sma20_val) / sma20_val) * 100 if sma20_val > 0 else 0
    
    # 3. BB 밴드폭 계산
    bb_std = close.rolling(20).std()
    bb_width_series = pd.Series(0.0, index=close.index)
    valid_idx = sma20 > 0
    bb_width_series[valid_idx] = ((sma20[valid_idx] + 2*bb_std[valid_idx]) - (sma20[valid_idx] - 2*bb_std[valid_idx])) / sma20[valid_idx]
    
    bb_mean = bb_width_series.rolling(20).mean().iloc[-1]
    
    return {
        'change_rate': change_rate,
        'deviation': deviation,
        'bb_mean': bb_mean,
        'bb_width_series': bb_width_series
    }

def get_signal_priority(trend, trend_prev, wt1, wt2, obv_confirmed, sq, df, market_type='KR', index_trend=1):
    """
    초심(Back to Basics) 정석 추세 추종 로직
    [매수] 20/60 정배열 + 20 우상향 + OBV 상승 + MACD 골크
    [매도] ST 하락 전환 또는 20일선 이탈
    """
    
    # ── 1. 기초 데이터 및 거래량 ──
    close = df['Close']
    close_p = float(close.iloc[-1])
    
    vol_curr = float(df['Volume'].iloc[-1])
    vol_ma20 = sq.get('vol_ma20', 0)
    vol_ratio = (vol_curr / vol_ma20) if vol_ma20 > 0 else 0

    # ── 2. 이동평균선 및 이격도 (정배열/우상향 판별) ──
    sma20 = close.rolling(20).mean()
    sma60 = close.rolling(60).mean()

    sma20_curr = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else close_p
    sma20_prev = float(sma20.iloc[-2]) if not pd.isna(sma20.iloc[-2]) else close_p
    sma60_curr = float(sma60.iloc[-1]) if not pd.isna(sma60.iloc[-1]) else close_p

    # [조건 1] 20일선 > 60일선 (정배열)
    is_golden_alignment = sma20_curr > sma60_curr
    
    # [조건 2] 20일선 우상향
    is_sma20_rising = sma20_curr >= sma20_prev

    # [위험 차단] 20일선/60일선 이격도 과열 (상투 잡기 방지)
    # 시장별 이격도 한계치 (KR: 15%, US: 20%, COIN: 25%)
    sma_gap_ratio = ((sma20_curr - sma60_curr) / sma60_curr) * 100 if sma60_curr > 0 else 0
    gap_limit = 15 if market_type == 'KR' else (25 if market_type == 'COIN' else 20)
    is_sma_overheated = sma_gap_ratio > gap_limit

    # ── 3. MACD 모멘텀 (방아쇠) ──
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_sig = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_sig
    
    macd_hist_curr = float(macd_hist.iloc[-1])
    macd_hist_prev = float(macd_hist.iloc[-2])

    # [조건 3] MACD 첫 골든크로스 (히스토그램 마이너스 -> 플러스 돌파)
    is_macd_golden_cross = (macd_hist_curr > 0) and (macd_hist_prev <= 0)

    # ── 4. 청산(매도) 시그널 ──
    is_st_down_turned = (trend == -1) and (trend_prev == 1)
    is_price_broken_sma20 = close_p < sma20_curr

    # ── 5. 🎯 최종 시그널 판정 (우선순위) ──
    
    # 🚨 [매도 청산 최우선]: ST 하락 전환 또는 20일선 이탈 시 기계적 청산
    if is_st_down_turned:
        s = ("📉 매도 (추세 꺾임)", "b01", 5, "SuperTrend 하락 전환. 보유량 전량 익절/손절")
    elif is_price_broken_sma20:
        s = ("📉 익절/손절 주의 (20일선 이탈)", "b01", 5, "단기 생명선(20일선) 하향 이탈. 리스크 관리")
    elif trend == -1:
        s = ("📉 하락 추세 지속", "c04", 5, "하락 추세 진행 중. 진입 금지")

    # 🛑 [상위 필터]: 거시 지수 하락 시 타점 무시
    elif is_macd_golden_cross and index_trend == -1:
        s = ("⚠️ 매수 보류 (시장 지수 하락)", "c02", 0, "종목 타점 발생했으나 거시 시장 역배열. 관망")

    # 🛑 [위험 차단]: 장기 이격도 과열 또는 유령 거래량 차단
    elif is_macd_golden_cross and is_sma_overheated:
        s = ("⚠️ 추격 금지 (이평선 과열)", "b03", 4, f"20/60일선 간격({sma_gap_ratio:.1f}%) 상투권. 진입 보류")
    elif is_macd_golden_cross and vol_ratio < 0.3:
        s = ("↔️ 관망 (거래량 부족)", "c02", 0, "MACD 교차했으나 거래량 실리지 않음. 가짜 신호 주의")

    # 🥇 [매수 진입 - A급]: 요청하신 완벽한 정석 타점
    elif is_macd_golden_cross and is_golden_alignment and is_sma20_rising and obv_confirmed:
        s = ("🚀 정석 매수 (A급 타점)", "a01", 1, "20일선 우상향 정배열 + OBV 상승 + MACD 골크")

    # 🥈 [매수 진입 - B급]: 정배열은 아니지만 20일선이 고개를 든 바닥 턴어라운드 (선택)
    elif is_macd_golden_cross and is_sma20_rising and obv_confirmed:
        s = ("🔥 바닥 탈출 (B급 타점)", "a02", 2, "20일선 우상향 턴 + MACD 골크. 60일선 저항 주의")

    # 🔄 [홀딩]: 골크 이후 순항 중
    elif macd_hist_curr > 0 and is_golden_alignment and is_sma20_rising:
        s = ("✅ 상승 추세 진행 중", "a05", 3, "20일선 정배열 추세 유지 중")

    else:
        s = ("↔️ 횡보/관망", "c02", 0, "뚜렷한 진입/청산 타점 부재")

    # DB 호환성을 위해 리턴 포맷은 기존과 100% 동일하게 유지
    return {
        'signal':        s[0],
        'signal_code':   s[1],
        'priority':      s[2],
        'action':        s[3],
        'wt_cross_up':   is_macd_golden_cross,  # 프론트에서 교체 없이 MACD 크로스를 인식하도록 맵핑
        'wt_cross_down': is_st_down_turned,
        'wt_oversold':   False,
        'wt_overbought': is_sma_overheated,
        'wt_momentum':   round(macd_hist_curr - macd_hist_prev, 4),
        'wt1':           round(macd_hist_curr, 4), # MACD 값 전달
        'wt2':           round(macd_hist_prev, 4),
    }

# def get_signal_priority(trend, trend_prev, wt1, wt2, obv_confirmed, sq, df, market_type='KR'):
#     """우선순위 및 손익비(리스크) 기반 시그널 판정 (응축 돌파 선취매 로직 포함)"""
    
#     # ── 1. 지표 상태 변수 계산 ──
#     wt1_curr  = float(wt1.iloc[-1])
#     wt2_curr  = float(wt2.iloc[-1])
#     wt1_prev  = float(wt1.iloc[-2])
#     wt2_prev  = float(wt2.iloc[-2])

#     wt_cross_up   = (wt1_curr > wt2_curr) and (wt1_prev <= wt2_prev)
#     wt_cross_down = (wt1_curr < wt2_curr) and (wt1_prev >= wt2_prev)
#     wt_oversold   = wt1_curr < -60
#     wt_oversold_mid = wt1_curr < -40
#     wt_overbought = wt1_curr > 60
#     wt_rising     = wt1_curr > wt1_prev

#     sr    = sq.get('squeeze_released', False)
#     vs    = sq.get('vol_surge', False)
#     is_sq = sq.get('is_squeeze', False)

#     close         = df['Close']
#     close_p       = float(close.iloc[-1])
#     prev_close    = float(close.iloc[-2]) if len(close) > 1 else close_p
    
#     vol_curr      = float(df['Volume'].iloc[-1])
#     vol_ma20      = sq.get('vol_ma20', 0)
#     vol_ratio     = (vol_curr / vol_ma20) if vol_ma20 > 0 else 0
#     change_rate   = ((close_p - prev_close) / prev_close) * 100
    
#     # ── 2. 이동평균선 및 이격도 (5, 10, 20, 60일) ──
#     sma5 = close.rolling(5).mean()
#     sma10 = close.rolling(10).mean()
#     sma20 = close.rolling(20).mean()
#     sma60 = close.rolling(60).mean()

#     sma5_val = float(sma5.iloc[-1]) if not pd.isna(sma5.iloc[-1]) else close_p
#     sma10_val = float(sma10.iloc[-1]) if not pd.isna(sma10.iloc[-1]) else close_p
#     sma20_val = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else close_p
#     sma60_val = float(sma60.iloc[-1]) if not pd.isna(sma60.iloc[-1]) else close_p

#     deviation     = ((close_p - sma20_val) / sma20_val) * 100 if sma20_val > 0 else 0
#     deviation_60  = ((close_p - sma60_val) / sma60_val) * 100 if sma60_val > 0 else 0

#     # ── 3. MACD 및 볼린저 밴드 ──
#     ema12 = close.ewm(span=12, adjust=False).mean()
#     ema26 = close.ewm(span=26, adjust=False).mean()
#     macd_line = ema12 - ema26
#     macd_sig = macd_line.ewm(span=9, adjust=False).mean()
#     macd_hist = float((macd_line - macd_sig).iloc[-1])

#     bb_mid = sma20
#     bb_std = close.rolling(20).std()
#     bb_width_series = pd.Series(0.0, index=close.index)
#     valid_idx = bb_mid > 0
#     bb_width_series[valid_idx] = ((bb_mid[valid_idx] + 2*bb_std[valid_idx]) - (bb_mid[valid_idx] - 2*bb_std[valid_idx])) / bb_mid[valid_idx]
    
#     bb_mean = bb_width_series.rolling(20).mean().iloc[-1]
#     is_bb_valid = not pd.isna(bb_mean)
#     bb_was_narrow = (bb_width_series.iloc[-5:].min() < bb_mean * 0.7) if is_bb_valid else False
#     bb_already_expanded = (bb_width_series.iloc[-1] > bb_mean * 1.3) if is_bb_valid else False

#     st_just_turned_up = (trend == 1) and (trend_prev == -1)

#     # ── 4. 🚨 위험 필터 (과열 및 가짜 반등 감지) ──
#     dev_limit = 15 if market_type == 'KR' else (30 if market_type == 'COIN' else 20)
#     alt_limit = 15 if market_type == 'KR' else 25 # ETF/국내주식은 60일선 15% 이상이면 고도 높음
    
#     is_ghost_tick = vol_ratio < 0.5 
#     is_high_altitude = deviation_60 > alt_limit  
    
#     # 5일선이 10일선 데드크로스 났거나 하락 중이면 박스권 고점 후 하락 징후
#     is_box_top = (sma5_val < sma10_val) or (float(sma5.iloc[-1]) < float(sma5.iloc[-2]))
#     is_momentum_dead = (macd_hist < 0) or is_box_top

#     is_chasing    = (change_rate > 10) or bb_already_expanded or (deviation > dev_limit) or is_high_altitude
#     is_pullback   = abs(deviation) < 10

#     # 🎯 [핵심 추가] 파란펜 타점: ST 전환 여부와 상관없이 BB수축 + WT골크 + 거래량 동반 시
#     is_squeeze_breakout = bb_was_narrow and wt_cross_up and (vol_ratio >= 1.0 or vs)

#     # ── 5. 최우선 판정 로직 ──
    
#     # 최상위 위험 필터
#     if (st_just_turned_up or sr or wt_cross_up) and is_ghost_tick:
#         s = ("↔️ 관망 (거래량 부족)", "c02", 0, f"거래량 배수({vol_ratio:.2f}) 미달. 속임수 방지")
#     elif (st_just_turned_up or sr or wt_cross_up or is_squeeze_breakout) and is_chasing and not is_pullback:
#         s = ("⚠️ 추격 금지 (폭발 후 과열/고점)", "b03", 4, "단기/중기 이격도 과열 또는 BB확장. 진입 보류")
        
#     # 🥇 [S급/A급 특례]: 응축 돌파 선취매 (사용자가 짚은 파란펜 타점!)
#     elif is_squeeze_breakout and not is_high_altitude:
#         s = ("🔥 응축 돌파 (A급 타점)", "a01", 1, "수축 구간에서 거래량 동반 상승 돌파. 선취매 타점")

#     # 🥇 [S급]: 폭발 초입 (이미 돌파되어 ST까지 전환된 가장 확실한 자리)
#     elif st_just_turned_up and bb_was_narrow and vs and wt_rising and not is_high_altitude:
#         s = ("🚀 폭발 초입 (S급 타점)", "a00", 1, "BB수축+ST전환+거래량 폭발. 상승 초입")
        
#     # 🥈 [A급]: 눌림목 반등 (진짜 눌림목 검증 추가)
#     # 조건 1: deviation < 5 (10%는 ETF에 너무 넓음. 20일선에 더 가까이 붙어야 함)
#     # 조건 2: wt1_curr < 20 (파동 지표가 상단(과매수)에서 노는 게 아니라, 0선 부근이나 그 아래까지 충분히 식은 상태에서 크로스 나야 함)
#     elif trend == 1 and wt_cross_up and obv_confirmed and deviation < 5 and wt1_curr < 20 and not is_high_altitude and not is_momentum_dead:
#     # 🥈 [A급]: 눌림목 반등 (정상적인 추세 진행 중 눌림목)
#     # elif trend == 1 and wt_cross_up and obv_confirmed and deviation < 10 and not is_high_altitude and not is_momentum_dead:
#         if wt_oversold_mid:
#             s = ("🔥 눌림목 반등 (A급 — 과매도)", "a01", 2, "안전한 20일선 지지 반등")
#         else:
#             s = ("🔥 눌림목 반등 (A급 타점)", "a01", 2, "안전한 20일선 부근 지지 후 반등")
            
#     # 🥉 [B급 이하]: 모멘텀이 둔화되었거나 고점이 가까워진 경우
#     elif trend == 1 and wt_cross_up:
#         s = ("✅ 매수 보류 (추세 확인 요망)", "a02", 3, "지표 피로도 누적(MACD/단기이평 하락). 신규 진입 자제")

#     # 🔄 [대기]: 응축 진행 중
#     elif bb_was_narrow and wt_rising:
#         if is_sq:
#             s = ("↔️ 응축 중 (방향 탐색)", "a03", 3, "수축 진행 중. 방향 확정 대기")
#         else:
#             s = ("↔️ 응축 해제 대기 (돌파 전)", "a03", 3, "수축 해제됨. 확실한 거래량/ST 전환 대기")

#     # ── 6. 익절 및 매도 로직 ──
#     elif trend == 1 and wt_overbought and wt_cross_down:
#         s = ("⚠️ 고점 주의 (신규 진입 금지)", "b03", 4, "과매수 구간 WT 데드크로스. 익절 고려")
#     elif trend == 1 and wt_overbought:
#         s = ("⚠️ 과매수 (보유 유지, 신규 금지)", "b03", 4, "과매수 구간 진입")
#     elif trend == -1 and wt_cross_up and wt_oversold and obv_confirmed:
#         s = ("📉 단기 바닥 포착 (낙폭 과대)", "a04", 5, "하락추세 중 극단 과매도 반등. 단기 매매만")
#     elif trend == -1 and wt_cross_down:
#         s = ("📉 매도 (하락 가속)", "b01", 5, "하락추세 + WT 데드크로스. 보유 청산 고려")
#     elif trend == -1 and not wt_rising:
#         s = ("📉 하락 추세 지속", "c04", 5, "하락추세 유지 중. 진입 금지")
#     else:
#         s = ("↔️ 방향 탐색 중", "c02", 0, "추세 불명확. 대기")

#     return {
#         'signal':        s[0],
#         'signal_code':   s[1],
#         'priority':      s[2],
#         'action':        s[3],
#         'wt_cross_up':   wt_cross_up,
#         'wt_cross_down': wt_cross_down,
#         'wt_oversold':   wt_oversold,
#         'wt_overbought': wt_overbought,
#         'wt_momentum':   round(wt1_curr - wt1_prev, 4),
#         'wt1':           round(wt1_curr, 4),
#         'wt2':           round(wt2_curr, 4),
#     }

# def get_signal_priority(trend, trend_prev, wt1, wt2, obv_confirmed, sq, df, market_type='KR'):
#     """우선순위 및 손익비(리스크) 기반 시그널 판정 (고점 횡보, MACD, 60일선 필터 완벽 적용)"""
#     wt1_curr  = float(wt1.iloc[-1])
#     wt2_curr  = float(wt2.iloc[-1])
#     wt1_prev  = float(wt1.iloc[-2])
#     wt2_prev  = float(wt2.iloc[-2])

#     wt_cross_up   = (wt1_curr > wt2_curr) and (wt1_prev <= wt2_prev)
#     wt_cross_down = (wt1_curr < wt2_curr) and (wt1_prev >= wt2_prev)
#     wt_oversold   = wt1_curr < -60
#     wt_oversold_mid = wt1_curr < -40
#     wt_overbought = wt1_curr > 60
#     wt_rising     = wt1_curr > wt1_prev

#     sr    = sq.get('squeeze_released', False)
#     vs    = sq.get('vol_surge', False)
#     is_sq = sq.get('is_squeeze', False)

#     # ✅ 1. 상태 변수 계산 (등락률, 20/60일 이격도, 거래량, MACD 등)
#     close         = df['Close']
#     close_p       = float(close.iloc[-1])
#     prev_close    = float(close.iloc[-2]) if len(close) > 1 else close_p
    
#     # 거래량 배수 산출
#     vol_curr      = float(df['Volume'].iloc[-1])
#     vol_ma20      = sq.get('vol_ma20', 0)
#     vol_ratio     = (vol_curr / vol_ma20) if vol_ma20 > 0 else 0
    
#     # 당일 등락률
#     change_rate   = ((close_p - prev_close) / prev_close) * 100
    
#     # 20일선 및 단기 이격도
#     sma20         = close.rolling(20).mean()
#     sma20_val     = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else close_p
#     deviation     = ((close_p - sma20_val) / sma20_val) * 100 if sma20_val > 0 else 0

#     # 60일선 및 중기 이격도 (고도계 역할)
#     sma60         = close.rolling(60).mean()
#     sma60_val     = float(sma60.iloc[-1]) if not pd.isna(sma60.iloc[-1]) else close_p
#     deviation_60  = ((close_p - sma60_val) / sma60_val) * 100 if sma60_val > 0 else 0

#     # ➕ 단기 이평선(5일, 10일) 추가 산출 (고점 쌍봉 및 가짜 반등 판별용)
#     sma5 = close.rolling(5).mean()
#     sma10 = close.rolling(10).mean()
#     sma5_val = float(sma5.iloc[-1]) if not pd.isna(sma5.iloc[-1]) else close_p
#     sma10_val = float(sma10.iloc[-1]) if not pd.isna(sma10.iloc[-1]) else close_p

#     # MACD 피로도 산출 (데드크로스 여부 파악)
#     ema12 = close.ewm(span=12, adjust=False).mean()
#     ema26 = close.ewm(span=26, adjust=False).mean()
#     macd_line = ema12 - ema26
#     macd_sig = macd_line.ewm(span=9, adjust=False).mean()
#     macd_hist = float((macd_line - macd_sig).iloc[-1])

#     # BB 밴드폭 계산 (0 나누기 방지)
#     bb_mid        = sma20
#     bb_std        = close.rolling(20).std()
#     bb_width_series = pd.Series(0.0, index=close.index)
#     valid_idx = bb_mid > 0
#     bb_width_series[valid_idx] = ((bb_mid[valid_idx] + 2*bb_std[valid_idx]) - (bb_mid[valid_idx] - 2*bb_std[valid_idx])) / bb_mid[valid_idx]
    
#     bb_mean       = bb_width_series.rolling(20).mean().iloc[-1]
    
#     st_just_turned_up = (trend == 1) and (trend_prev == -1)
    
#     # 5봉 기준 수축 검증
#     is_bb_valid = not pd.isna(bb_mean)
#     bb_was_narrow = (bb_width_series.iloc[-5:].min() < bb_mean * 0.7) if is_bb_valid else False
#     bb_already_expanded = (bb_width_series.iloc[-1] > bb_mean * 1.3) if is_bb_valid else False

#     # 시장별 이격도 한계치 자동 설정
#     dev_limit_map = {'KR': 15, 'US': 20, 'COIN': 30}
#     dev_limit = dev_limit_map.get(market_type, 15)

#     # ✅ 2. [위험 필터] 고점 피로도 및 시장별 한계치 세분화
#     # 시장 특성(KR/ETF)을 고려해 60일선 고도계 기준을 15%로 타이트하게 조정
#     alt_limit = 15 if market_type == 'KR' else 25
#     is_high_altitude = deviation_60 > alt_limit

#     # ➕ 고점 박스권 횡보/하락 징후 확인
#     # 5일선이 10일선 아래에 있거나 전일 대비 꺾인 경우 속임수 반등으로 간주
#     is_box_top = (sma5_val < sma10_val) or (float(sma5.iloc[-1]) < float(sma5.iloc[-2]))

#     # 모멘텀 데드 조건 강화: MACD가 양수여도 단기 이평이 죽어있으면 진입 차단
#     is_momentum_dead = (macd_hist < 0) or is_box_top

#     # 위험 필터 종합
#     is_ghost_tick = vol_ratio < 0.5 
#     is_chasing    = (change_rate > 10) or bb_already_expanded or (deviation > dev_limit) or is_high_altitude
#     is_pullback   = abs(deviation) < 10

#     # ⚠️ [최상위 필터 1]: 거래량 부족 시 가짜 신호 차단
#     if (st_just_turned_up or sr or wt_cross_up) and is_ghost_tick:
#         s = ("↔️ 관망 (거래량 부족)", "c02", 0, f"거래량 배수({vol_ratio:.2f}) 미달. 가짜 반등 방지")

#     # ⚠️ [최상위 필터 2]: 단기/중장기 과열 추격 금지
#     elif (st_just_turned_up or sr or wt_cross_up) and is_chasing and not is_pullback:
#         s = ("⚠️ 추격 금지 (폭발 후 과열/고점)", "b03", 4, "단기/중기 이격도 과열 또는 BB확장. 진입 보류")
        
#     # 🥇 [1순위 S급]: 폭발 초입 (60일선 고도계가 정상일 때만)
#     elif st_just_turned_up and bb_was_narrow and vs and wt_rising and obv_confirmed and deviation < 10 and not is_high_altitude:
#         s = ("🚀 폭발 초입 (즉시 진입)", "a00", 1, "BB수축+ST전환+거래량. 손익비 최상 타점")
        
#     # 🥈 [2순위 A급]: 눌림목 반등 (MACD 모멘텀이 살아있고 고점이 아닐 때만 허용)
#     elif trend == 1 and wt_cross_up and obv_confirmed and deviation < 10 and not is_high_altitude and not is_momentum_dead:
#         if wt_oversold_mid:
#             s = ("🔥 눌림목 반등 (A급 — 과매도)", "a01", 2, "상승 추세 내 안전한 20일선 지지 반등")
#         else:
#             s = ("🔥 눌림목 반등 (A급 타점)", "a01", 2, "상승 추세 내 20일선 부근 지지 후 반등")

#     # 🥉 [3순위 B급]: 상승 중이긴 하나, 피로도가 높거나 고점이 다가오는 경우 (비중 축소)
#     elif trend == 1 and wt_cross_up:
#         s = ("✅ 매수 보류 (추세 확인 요망)", "a02", 3, "지표 피로도 누적 및 고점 도달 우려. 신규 진입 자제")

#     # 🔄 [대기]: 응축 상태 분기 처리
#     elif bb_was_narrow and wt_rising:
#         if is_sq:
#             s = ("↔️ 응축 중 (ST 전환 대기)", "a03", 3, "수축 진행 중. 방향 확정 대기")
#         else:
#             s = ("↔️ 응축 해제 대기 (ST 전환 전)", "a03", 3, "수축 해제됨. ST 전환 확인 후 진입")

#     # ✅ 4. 기타 매도 및 하락 관리 로직
#     elif trend == 1 and wt_overbought and wt_cross_down:
#         s = ("⚠️ 고점 주의 (신규 진입 금지)", "b03", 4, "과매수 구간 WT 꺾임. 기존 보유자 익절 고려")
#     elif trend == 1 and wt_overbought:
#         s = ("⚠️ 과매수 (보유 유지, 신규 금지)", "b03", 4, "과매수 구간. 신규 진입 자제")
#     elif trend == -1 and wt_cross_up and wt_oversold and obv_confirmed:
#         s = ("📉 찐바닥 포착 (단기 반등)", "a04", 5, "하락추세 중 극단 과매도 반등. 단기 매매만")
#     elif trend == -1 and wt_cross_down:
#         s = ("📉 매도 (하락 가속)", "b01", 5, "하락추세 + WT 데드크로스. 보유 청산 고려")
#     elif trend == -1 and not wt_rising:
#         s = ("📉 하락 추세 지속", "c04", 5, "하락추세 유지 중. 진입 금지")
#     else:
#         s = ("↔️ 방향 탐색 중", "c02", 0, "추세 불명확. 대기")

#     return {
#         'signal':        s[0],
#         'signal_code':   s[1],
#         'priority':      s[2],
#         'action':        s[3],
#         'wt_cross_up':   wt_cross_up,
#         'wt_cross_down': wt_cross_down,
#         'wt_oversold':   wt_oversold,
#         'wt_overbought': wt_overbought,
#         'wt_momentum':   round(wt1_curr - wt1_prev, 4),
#         'wt1':           round(wt1_curr, 4),
#         'wt2':           round(wt2_curr, 4),
#     }

def calc_t_signal(df, wt1, wt2):
    """T 신호등 (HMA + WaveTrend)"""
    df = df.copy()
    df['HMA'] = calc_hma(df['Close'], 14)
    hma_up = df['HMA'].iloc[-1] > df['HMA'].iloc[-2]
    wt_up  = (wt1.iloc[-1] > wt2.iloc[-1]) and (wt1.iloc[-1] > wt1.iloc[-2])
    return 'green' if hma_up and wt_up else ('red' if not hma_up and not wt_up else 'orange')

def calc_n_signal(df, close_p, macd, macd_sig, obv):
    """N 신호등 (SMA20 + MACD + OBV)"""
    sma20    = df['Close'].rolling(20).mean()
    obv_sma20 = obv.rolling(20).mean()
    price_up = close_p > float(sma20.iloc[-1])
    macd_up  = float(macd.iloc[-1]) > float(macd_sig.iloc[-1])
    obv_up   = (
        float(obv_sma20.iloc[-1]) > float(obv_sma20.iloc[-5]) and
        float(obv.iloc[-1]) > float(obv.iloc[-20])
    )
    score = sum([price_up, macd_up, obv_up])
    return 'green' if score == 3 else ('red' if score == 0 else 'orange')

def calc_up_days(close: pd.Series) -> int:
    """연속 상승일 수"""
    diff    = close.diff().dropna()
    up_days = 0
    for v in diff.iloc[::-1]:
        if v > 0: up_days += 1
        else: break
    return up_days