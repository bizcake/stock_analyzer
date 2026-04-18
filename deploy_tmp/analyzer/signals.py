from .constants import SIGNAL_MAP
def get_final_signal_with_code(rsi, hist_up, macd_cross, obv_confirmed, curr_p, s5, s5_prev, s20, s120, stoch_k, stoch_d, stoch_cross):
    """지표를 받아 텍스트 신호와 공통 코드(a01 등)를 동시에 반환"""
    final_signal = "Hold (관망)"
    
    s5_up = s5 > s5_prev
    is_bull_market = (curr_p > s120) or (s20 > s120)

    # 스토캐스틱 임계값 동적 적용 (상승장에서는 60 이하 골든크로스도 유효)
    stoch_threshold = 60 if is_bull_market else 40
    stoch_buy_trigger = stoch_cross and (stoch_k < stoch_threshold)

    # 이격도 (현재가와 20일선의 이격률) - 눌림목 판단용 (-3% ~ 7% 허용)
    deviation = (curr_p - s20) / s20 if s20 != 0 else 0
    is_pullback = -0.03 <= deviation <= 0.07

    # RSI 과매수 임계값 동적 적용 (상승장에서는 75까지 허용)
    rsi_threshold = 75 if is_bull_market else 65

    if s5 > s20:
        if s5_up:
            if hist_up and obv_confirmed:
                if (macd_cross or stoch_buy_trigger) and rsi < rsi_threshold:
                    if is_pullback:
                        final_signal = "🔥 강력 매수 (완벽한 눌림목 타점)" if is_bull_market else "✅ 매수 (바닥탈출 시도)"
                    else:
                        final_signal = "🔥 강력 매수 (추세 돌파/지속)" if is_bull_market else "✅ 매수 (상승 추세 강화)"
                else:
                    final_signal = "✅ 매수 (상승 추세 지속)" if is_bull_market else "↔️ 기술적 반등 (저항주의)"
            else:
                final_signal = "↔️ 방향 탐색 중"
        else:
            # [수정됨] 5일선이 꺾였더라도 주가가 5일선을 지지하거나 MACD 모멘텀이 살아있으면 횡보/눌림목으로 판정
            # if curr_p >= s5 or hist_up:
            if curr_p >= (s5 * 0.98) or hist_up:
                final_signal = "↔️ 단기 눌림목 (추세 관찰)" if is_bull_market else "↔️ 상승 후 횡보 (방향 탐색 중)"
            else:
                final_signal = "⚠️ 관망 (단기 고점 의심)" if is_bull_market else "⚠️ 매도 주의 (반등 끝자락)"
    else:
        if s5_up:
            # 찐바닥 포착 시 가장 중요한 obv_confirmed(수급) 조건 추가
            if (macd_cross or stoch_buy_trigger) and hist_up and obv_confirmed and rsi < 40:
                final_signal = "📉 찐바닥 포착 (매수 대기)"
            else:
                final_signal = "📉 기술적 반등 시도 (관망)"
        else:
            # RSI 과매도 구간 이탈이나 급격한 꺾임도 매도 트리거로 추가
            if (curr_p < s5 and not is_bull_market) or (rsi > 75 and not hist_up):
                final_signal = "📉 매도 (추세이탈)"
            else:
                final_signal = "📉 하락 추세 지속 (관망)"

    return final_signal, SIGNAL_MAP.get(final_signal, "d01")

def analyze_candle_pattern(open_p, high_p, low_p, close_p, prev_close, atr_14=0):
    candle_length = high_p - low_p
    if candle_length == 0:
        return 'gray', 'p04', '도지/단봉 (관망)'

    body = abs(close_p - open_p)
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p

    # 갭(Gap) 여부 플래그 추가
    gap_up = open_p > prev_close * 1.01
    gap_down = open_p < prev_close * 0.99
    gap_str = ' (갭상승)' if gap_up else (' (갭하락)' if gap_down else '')

    if (body / candle_length) < 0.1:
        return 'gray', 'p04', '도지/단봉 (관망)'

    # ATR이 주어진 경우 ATR 기준 70% 이상을 장대봉으로 판단, 없으면 기존 5% 룰 유지
    long_body_threshold = atr_14 * 0.7 if atr_14 > 0 else prev_close * 0.05

    if close_p > open_p:
        if lower_shadow > body * 2.0: 
            return 'green', 'p01', f'망치형 (매수세 강함){gap_str}'
        elif upper_shadow > body * 2.0: 
            return 'orange', 'p03', f'역망치형 (매물 출회){gap_str}'
        else:
            is_long = body > long_body_threshold
            return ('green', 'p07', f'장대양봉{gap_str}') if is_long else ('orange', 'p02', f'단봉(양){gap_str}')
    else:
        if upper_shadow > body * 2.0: 
            return 'red', 'p06', f'유성형 (하락 반전){gap_str}'
        elif lower_shadow > body * 2.0: 
            return 'orange', 'p08', f'교수형 (지지 확인){gap_str}'
        else:
            is_long = body > long_body_threshold
            return ('red', 'p09', f'장대음봉{gap_str}') if is_long else ('orange', 'p05', f'단봉(음){gap_str}')
