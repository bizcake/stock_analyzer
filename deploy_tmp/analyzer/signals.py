from .constants import SIGNAL_MAP

def get_final_signal_with_code(
    rsi, hist_up, macd_cross, obv_confirmed, curr_p,
    s5, s5_prev, s5_prev2,   # s5_prev2 추가
    s20, s120,
    stoch_k, stoch_d, stoch_cross
):
    final_signal = "Hold (관망)"

    # ✅ 수정1: 2봉 연속으로 추세 판단
    s5_up          = s5 > s5_prev
    s5_up_prev     = s5_prev > s5_prev2
    s5_strongly_up = s5_up and s5_up_prev        # 2봉 연속 상승
    s5_strongly_dn = not s5_up and not s5_up_prev # 2봉 연속 하락

    # ✅ 수정2: 상승장 3단계 구분
    strong_bull    = (curr_p > s120) and (s20 > s120)
    weak_bull      = (curr_p > s120) or  (s20 > s120)
    is_bull_market = weak_bull

    # 스토캐스틱 임계값
    stoch_threshold   = 60 if is_bull_market else 40
    stoch_buy_trigger = stoch_cross and (stoch_k < stoch_threshold)

    # 이격도
    deviation   = (curr_p - s20) / s20 if s20 != 0 else 0
    is_pullback = -0.05 <= deviation <= 0.07  # 하락 허용 범위 확대

    # RSI 임계값
    rsi_threshold = 75 if strong_bull else (70 if weak_bull else 65)

    # ✅ 수정3: MACD 신호 신뢰도 강화
    # 크로스 직후 1봉만이 아닌 히스토그램 확대 동반 여부
    macd_confirmed = macd_cross and hist_up  # 크로스 + 모멘텀 동반

    # ─────────────────────────────────
    # 메인 로직
    # ─────────────────────────────────
    if s5 > s20:
        if s5_up:
            if hist_up and obv_confirmed:
                if (macd_confirmed or stoch_buy_trigger) and rsi < rsi_threshold:
                    if is_pullback:
                        final_signal = "🔥 강력 매수 (완벽한 눌림목 타점)" if strong_bull \
                                  else "✅ 매수 (바닥탈출 시도)"
                    else:
                        final_signal = "🔥 강력 매수 (추세 돌파/지속)" if strong_bull \
                                  else "✅ 매수 (상승 추세 강화)"
                else:
                    final_signal = "✅ 매수 (상승 추세 지속)" if is_bull_market \
                              else "↔️ 기술적 반등 (저항주의)"
            else:
                final_signal = "↔️ 방향 탐색 중"

        else:  # s5 꺾임
            if s5_strongly_dn:
                # 2봉 연속 하락일 때만 경고
                final_signal = "⚠️ 관망 (단기 고점 의심)" if is_bull_market \
                          else "⚠️ 매도 주의 (반등 끝자락)"
            else:
                # 1봉 노이즈 → 눌림목 판단
                if curr_p >= (s5 * 0.98) or hist_up:
                    final_signal = "↔️ 단기 눌림목 (추세 관찰)" if is_bull_market \
                              else "↔️ 상승 후 횡보 (방향 탐색 중)"
                else:
                    final_signal = "⚠️ 관망 (단기 고점 의심)" if is_bull_market \
                              else "⚠️ 매도 주의 (반등 끝자락)"

    else:  # s5 < s20
        if s5_up:
            deep_discount   = deviation < -0.10
            reversal_signal = macd_confirmed or stoch_buy_trigger

            if deep_discount and reversal_signal and obv_confirmed:
                # 많이 빠진 상태 + 반등 신호 + 수급
                final_signal = "📉 찐바닥 포착 (매수 대기)"
            elif reversal_signal and hist_up and obv_confirmed and rsi < 40:
                # 기존 엄격 조건
                final_signal = "📉 찐바닥 포착 (매수 대기)"
            elif reversal_signal and hist_up:
                # 수급 미확인이지만 나머지 충족
                final_signal = "↔️ 기술적 반등 시도 (매수 검토)"
            else:
                final_signal = "📉 기술적 반등 시도 (관망)"

        else:  # s5 하락
            if s5_strongly_dn:
                # ✅ 수정4: 하락 구간 매도 조건 현실화
                # RSI > 75는 하락 중 거의 불가 → 제거
                # 가격이 5일선 아래 + 약세장이면 매도
                if curr_p < s5 and not is_bull_market:
                    final_signal = "📉 매도 (추세이탈)"
                elif not hist_up and not obv_confirmed:
                    # 모멘텀 + 수급 모두 약화
                    final_signal = "📉 매도 (추세이탈)"
                else:
                    final_signal = "📉 하락 추세 지속 (관망)"
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
