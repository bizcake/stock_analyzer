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

def get_signal_priority(trend, wt1, wt2, obv_confirmed, sq):
    """
    우선순위 기반 시그널 판정
    return: dict(signal, signal_code, priority, action, wt_*)
    """
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

    sr  = sq['squeeze_released']
    vs  = sq['vol_surge']

    # 우선순위 판정
    if sr and wt_cross_up and vs and obv_confirmed:
        s = ("🚀 적극 매수 (응축 돌파)", "a00", 1,
             "즉시 매수 검토. 응축해제+거래량급증+수급 확인")
    elif sr and wt_cross_up and trend == 1:
        s = ("🚀 적극 매수 (응축 돌파 — 추세확인)", "a00", 1,
             "상승추세 중 응축 해제. 거래량 추가 확인 권장")
    elif trend == 1 and wt_cross_up and wt_oversold and obv_confirmed:
        s = ("🔥 강력 매수 (눌림목 — 최적 타점)", "a01", 2,
             "상승추세 중 과매도 반등. 핵심 매수 타점")
    elif trend == 1 and wt_cross_up and wt_oversold_mid and obv_confirmed:
        s = ("🔥 강력 매수 (중간 눌림목)", "a01", 2,
             "상승추세 중 중간 눌림목 반등")
    elif trend == 1 and wt_cross_up and not wt_overbought:
        s = ("✅ 매수 (추세 지속)", "a02", 3,
             "상승추세 중 WT 골든크로스. 안전 진입 구간")
    elif trend == 1 and wt_rising and obv_confirmed and not wt_overbought:
        s = ("✅ 매수 (추세 상승 유지)", "a02", 3,
             "추세+수급 모두 우호적. 보유 또는 추가 매수")
    elif trend == 1 and wt_overbought and wt_cross_down:
        s = ("⚠️ 고점 주의 (신규 진입 금지)", "b03", 4,
             "과매수 구간 WT 꺾임. 기존 보유자 익절 고려")
    elif trend == 1 and wt_overbought:
        s = ("⚠️ 과매수 (보유 유지, 신규 금지)", "b03", 4,
             "과매수 구간. 신규 진입 자제")
    elif trend == -1 and wt_cross_up and wt_oversold and obv_confirmed:
        s = ("📉 찐바닥 포착 (단기 반등)", "a04", 5,
             "하락추세 중 극단 과매도 반등. 단기 매매만")
    elif trend == -1 and wt_cross_down:
        s = ("📉 매도 (하락 가속)", "b01", 5,
             "하락추세 + WT 데드크로스. 보유 청산 고려")
    elif trend == -1 and not wt_rising:
        s = ("📉 하락 추세 지속", "c04", 5,
             "하락추세 유지 중. 진입 금지")
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