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
    """
    df 컬럼: High, Low, Close
    return: direction(int), st_value(float), trend_series(Series)
    """
    high  = df['High'].values
    low   = df['Low'].values
    close = df['Close'].values

    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - np.roll(close, 1)),
            np.abs(low  - np.roll(close, 1))
        )
    )
    tr[0] = high[0] - low[0]
    atr = pd.Series(tr).rolling(period).mean().values

    src      = (high + low) / 2
    up_raw   = src - multiplier * atr
    dn_raw   = src + multiplier * atr
    up_level = up_raw.copy()
    dn_level = dn_raw.copy()
    trend    = np.ones(len(df), dtype=int)

    for i in range(1, len(df)):
        up_level[i] = max(up_raw[i], up_level[i-1]) \
                      if close[i-1] > up_level[i-1] else up_raw[i]
        dn_level[i] = min(dn_raw[i], dn_level[i-1]) \
                      if close[i-1] < dn_level[i-1] else dn_raw[i]

        if trend[i-1] == -1 and close[i] > dn_level[i-1]:
            trend[i] = 1
        elif trend[i-1] == 1 and close[i] < up_level[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]

    direction = int(trend[-1])
    st_value  = float(up_level[-1] if direction == 1 else dn_level[-1])
    return direction, st_value

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
    
def get_signal_priority(trend, trend_prev, wt1, wt2, obv_confirmed, sq, df, market_type='KR'):
    """우선순위 및 손익비(리스크) 기반 시그널 판정 (과열 추격 금지 및 타점 최적화)"""
    wt1_curr  = float(wt1.iloc[-1])
    wt2_curr  = float(wt2.iloc[-1])
    wt1_prev  = float(wt1.iloc[-2])
    wt2_prev  = float(wt2.iloc[-2])

    wt_cross_up   = (wt1_curr > wt2_curr) and (wt1_prev <= wt2_prev)
    wt_cross_down = (wt1_curr < wt2_curr) and (wt1_prev >= wt2_prev)
    wt_oversold   = wt1_curr < -60
    wt_oversold_mid = wt1_curr < -40
    wt_overbought = wt1_curr > 60
    wt_rising     = wt1_curr > wt1_prev

    # sq 딕셔너리 안전한 값 추출
    sr    = sq.get('squeeze_released', False)
    vs    = sq.get('vol_surge', False)
    is_sq = sq.get('is_squeeze', False)

    # ✅ 1. 상태 변수 계산 (등락률, 이격도, BB 밴드폭) - df 내부 연산 유지
    close         = df['Close']
    close_p       = float(close.iloc[-1])
    prev_close    = float(close.iloc[-2]) if len(close) > 1 else close_p

    # ➕ 거래량 배수 산출 (추가된 부분)
    vol_curr      = float(df['Volume'].iloc[-1])
    vol_ma20      = sq.get('vol_ma20', 0)
    vol_ratio     = (vol_curr / vol_ma20) if vol_ma20 > 0 else 0
    
    # 당일 등락률 및 이격도
    change_rate   = ((close_p - prev_close) / prev_close) * 100
    sma20         = close.rolling(20).mean()
    sma20_val     = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else close_p
    deviation     = ((close_p - sma20_val) / sma20_val) * 100 if sma20_val > 0 else 0

    # BB 밴드폭 계산 (0 나누기 방지)
    bb_mid        = sma20
    bb_std        = close.rolling(20).std()
    bb_width_series = pd.Series(0.0, index=close.index)
    valid_idx = bb_mid > 0
    bb_width_series[valid_idx] = ((bb_mid[valid_idx] + 2*bb_std[valid_idx]) - (bb_mid[valid_idx] - 2*bb_std[valid_idx])) / bb_mid[valid_idx]
    
    bb_mean       = bb_width_series.rolling(20).mean().iloc[-1]
    
    st_just_turned_up = (trend == 1) and (trend_prev == -1)
    
    # NaN 에러 방지 처리 및 5봉 기준 수축 검증 (신뢰도 상향)
    is_bb_valid = not pd.isna(bb_mean)
    bb_was_narrow = (bb_width_series.iloc[-5:].min() < bb_mean * 0.7) if is_bb_valid else False
    bb_already_expanded = (bb_width_series.iloc[-1] > bb_mean * 1.3) if is_bb_valid else False

    # ✅ 2. 시장별 이격도 한계치 자동 설정
    dev_limit_map = {'KR': 15, 'US': 20, 'COIN': 40}
    dev_limit = dev_limit_map.get(market_type, 15)

    # ✅ 3. [위험 필터] 과열 vs 눌림목 정밀 분리
    is_chasing  = (change_rate > 10) or bb_already_expanded or (deviation > dev_limit)
    is_pullback = abs(deviation) < 10

    # ➕ 거래량 가뭄 상태 판별 (평균 거래량의 50% 미만일 경우 속임수로 간주)
    is_ghost_tick = vol_ratio < 0.5

    # ✅ 4. 최우선 판정 로직 (리스크-리턴 기반)
    
    # ⚠️ [최상위 필터 1]: 거래량 부족 시 매수 시그널 차단 (신규 추가)
    if (st_just_turned_up or sr or wt_cross_up) and is_ghost_tick:
        s = ("↔️ 관망 (거래량 부족)", "c02", 0, f"거래량 배수({vol_ratio:.2f}) 미달. 가짜 신호 방지")

    # ⚠️ [최상위 필터 2]: 추격 금지 (상승장 안전한 눌림목은 보호하고, 고점 추격만 차단)
    elif (st_just_turned_up or sr or wt_cross_up) and is_chasing and not is_pullback:
        s = ("⚠️ 추격 금지 (폭발 후 과열)", "b03", 4, "등락률/이격도 과열 또는 BB확장. 진입 보류")
    
    # 🥇 [1순위 S급]: 폭발 초입
    elif st_just_turned_up and bb_was_narrow and vs and wt_rising and obv_confirmed and deviation < 10:
        s = ("🚀 폭발 초입 (즉시 진입)", "a00", 1, "BB수축(5봉)+ST전환+거래량급증. 손익비 최상 타점")
        
    # 🥈 [2순위 A급]: 눌림목 반등
    elif trend == 1 and wt_cross_up and obv_confirmed and deviation < 10:
        if wt_oversold_mid:
            s = ("🔥 눌림목 반등 (A급 — 과매도)", "a01", 2, "상승 추세 내 과매도권 20일선 지지 반등")
        else:
            s = ("🔥 눌림목 반등 (A급 타점)", "a01", 2, "상승 추세 내 20일선 부근 지지 후 반등")

    # ⚠️ [최상위 필터]: 추격 금지 (상승장 안전한 눌림목은 보호하고, 고점 추격만 차단)
    elif (st_just_turned_up or sr or wt_cross_up) and is_chasing and not is_pullback:
        s = ("⚠️ 추격 금지 (폭발 후 과열)", "b03", 4, f"등락률/이격도 과열 또는 BB확장. 진입 보류")
        
    # 🥇 [1순위 S급]: 폭발 초입 (과열되지 않은 상태에서 거래량 동반 폭발)
    elif st_just_turned_up and bb_was_narrow and vs and wt_rising and obv_confirmed and deviation < 10:
        s = ("🚀 폭발 초입 (즉시 진입)", "a00", 1, "BB수축(5봉)+ST전환+거래량급증. 손익비 최상 타점")
        
    # 🥈 [2순위 A급]: 눌림목 반등 (wt_oversold_mid 조건 분리하여 유연하게 적용)
    elif trend == 1 and wt_cross_up and obv_confirmed and deviation < 10:
        if wt_oversold_mid:
            s = ("🔥 눌림목 반등 (A급 — 과매도)", "a01", 2, "상승 추세 내 과매도권 20일선 지지 반등")
        else:
            s = ("🔥 눌림목 반등 (A급 타점)", "a01", 2, "상승 추세 내 20일선 부근 지지 후 반등")
            
    # 🥉 [3순위 B급]: 추세 지속 (시장별 이격도 한계치 적용)
    elif trend == 1 and wt_cross_up and not wt_overbought and deviation < dev_limit:
        s = ("✅ 매수 (추세 지속)", "a02", 3, f"이격도 {dev_limit}% 미만 안전 진입 구간")

    # 🔄 [대기]: 응축 상태 분기 처리 (is_squeeze 여부에 따라 정확히 구분)
    elif bb_was_narrow and wt_rising:
        if is_sq:
            s = ("↔️ 응축 중 (ST 전환 대기)", "a03", 3, "수축 진행 중. 방향 확정 대기")
        else:
            s = ("↔️ 응축 해제 대기 (ST 전환 전)", "a03", 3, "수축 해제됨. ST 전환 확인 후 진입")

    # ✅ 5. 기타 매도 및 하락 관리 로직
    elif trend == 1 and wt_overbought and wt_cross_down:
        s = ("⚠️ 고점 주의 (신규 진입 금지)", "b03", 4, "과매수 구간 WT 꺾임. 기존 보유자 익절 고려")
    elif trend == 1 and wt_overbought:
        s = ("⚠️ 과매수 (보유 유지, 신규 금지)", "b03", 4, "과매수 구간. 신규 진입 자제")
    elif trend == -1 and wt_cross_up and wt_oversold and obv_confirmed:
        s = ("📉 찐바닥 포착 (단기 반등)", "a04", 5, "하락추세 중 극단 과매도 반등. 단기 매매만")
    elif trend == -1 and wt_cross_down:
        s = ("📉 매도 (하락 가속)", "b01", 5, "하락추세 + WT 데드크로스. 보유 청산 고려")
    elif trend == -1 and not wt_rising:
        s = ("📉 하락 추세 지속", "c04", 5, "하락추세 유지 중. 진입 금지")
    else:
        s = ("↔️ 방향 탐색 중", "c02", 0, "추세 불명확. 대기")

    return {
        'signal':        s[0],
        'signal_code':   s[1],
        'priority':      s[2],
        'action':        s[3],
        'wt_cross_up':   wt_cross_up,
        'wt_cross_down': wt_cross_down,
        'wt_oversold':   wt_oversold,
        'wt_overbought': wt_overbought,
        'wt_momentum':   round(wt1_curr - wt1_prev, 4),
        'wt1':           round(wt1_curr, 4),
        'wt2':           round(wt2_curr, 4),
    }

#     """우선순위 기반 시그널 판정 (추격 금지 및 BB 밴드폭 필터 적용)"""
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

#     sr  = sq['squeeze_released']
#     vs  = sq['vol_surge']

#     # ✅ 1. 추가 로직: 상태 변수 계산 (BB 밴드폭 및 ST 전환)
#     close         = df['Close']
#     bb_mid        = close.rolling(20).mean()
#     bb_std        = close.rolling(20).std()
    
#     # 밴드폭 계산 (0 나누기 방지)
#     bb_width_series = pd.Series(0.0, index=close.index)
#     valid_idx = bb_mid > 0
#     bb_width_series[valid_idx] = ((bb_mid[valid_idx] + 2*bb_std[valid_idx]) - (bb_mid[valid_idx] - 2*bb_std[valid_idx])) / bb_mid[valid_idx]
    
#     bb_mean       = bb_width_series.rolling(20).mean().iloc[-1]
    
#     st_just_turned_up = (trend == 1) and (trend_prev == -1)
    
#     # NaN 에러 방지 처리 (상장 직후 데이터 부족 종목)
#     is_bb_valid = not pd.isna(bb_mean)
#     bb_was_narrow = (bb_width_series.iloc[-3:].min() < bb_mean * 0.7) if is_bb_valid else False
#     bb_already_expanded = (bb_width_series.iloc[-1] > bb_mean * 1.3) if is_bb_valid else False

#     # ✅ 2. 최우선 판정: 신규 타점 및 추격 금지
    
#     # ⚠️ [최상위 필터] 추격 금지: 이미 BB가 확장되었는데 ST가 뒤늦게 전환된 경우
#     if st_just_turned_up and bb_already_expanded:
#         s = ("⚠️ 추격 금지 (폭발 후 전환)", "b03", 4, "BB 이미 확대 완료. 눌림목 대기 후 재진입 권장")
        
#     # 🥇 [최상]: BB 수축 + ST 방금 전환 + 거래량 급증 + WT 상승 + 수급 (완벽한 타점)
#     elif st_just_turned_up and bb_was_narrow and vs and wt_rising and obv_confirmed:
#         s = ("🚀 응축 폭발 (즉시 진입)", "a00", 1, "BB수축+ST전환+거래량급증+WT상승. 최적 타점")
        
#     # 🥈 [상]: BB 수축 + ST 방금 전환
#     elif st_just_turned_up and bb_was_narrow:
#         s = ("🔥 응축 돌파 (ST 전환 확인)", "a01", 2, "BB수축+ST상향전환. 거래량 추가 확인 권장")
        
#     # 🥉 [중]: BB 수축 상태에서 WT 상승 (ST 전환 대기)
#     elif bb_was_narrow and wt_rising and not sq['is_squeeze']:
#         s = ("↔️ 응축 해제 대기 (ST 전환 확인 후 진입)", "a03", 3, "BB수축+WT상승. ST전환 확인 후 진입")

#     # ✅ 3. 기존 판정 (추세 진행 및 과매수/과매도 로직 유지)
#     elif sr and wt_cross_up and trend == 1:
#         s = ("🚀 적극 매수 (응축 돌파 — 추세확인)", "a00", 1, "상승추세 중 응축 해제. 거래량 추가 확인 권장")
#     elif trend == 1 and wt_cross_up and wt_oversold and obv_confirmed:
#         s = ("🔥 강력 매수 (눌림목 — 최적 타점)", "a01", 2, "상승추세 중 과매도 반등. 핵심 매수 타점")
#     elif trend == 1 and wt_cross_up and wt_oversold_mid and obv_confirmed:
#         s = ("🔥 강력 매수 (중간 눌림목)", "a01", 2, "상승추세 중 중간 눌림목 반등")
#     elif trend == 1 and wt_cross_up and not wt_overbought:
#         s = ("✅ 매수 (추세 지속)", "a02", 3, "상승추세 중 WT 골든크로스. 안전 진입 구간")
#     elif trend == 1 and wt_rising and obv_confirmed and not wt_overbought:
#         s = ("✅ 매수 (추세 상승 유지)", "a02", 3, "추세+수급 모두 우호적. 보유 또는 추가 매수")
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