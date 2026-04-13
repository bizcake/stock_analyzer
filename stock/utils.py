import os
import ssl
import logging
import time
import json
import random
import requests
import numpy as np
import pandas as pd
import certifi
import re
import yfinance as yf
from dotenv import load_dotenv
from .models import StockMaster

# --- [1. 시스템 및 보안 설정: 최상단 1회 설정] ---
load_dotenv()
logger = logging.getLogger(__name__)

# SSL 검증 무력화 (야후 및 AI API 통신용)
os.environ['CURL_CA_BUNDLE'] = ""
os.environ['REQUESTS_CA_BUNDLE'] = ""
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['SSL_CERT_FILE'] = ""

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# curl_cffi 패치 (설치된 경우에만)
try:
    from curl_cffi import requests as core_requests
    original_session_request = core_requests.Session.request
    def patched_request(self, method, url, *args, **kwargs):
        kwargs['verify'] = False
        return original_session_request(self, method, url, *args, **kwargs)
    core_requests.Session.request = patched_request
except ImportError:
    pass

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- [2. 공통 코드 매핑] ---
SIGNAL_MAP = {
    "🔥 강력 매수 (완벽한 눌림목 타점)": "a01",
    "✅ 매수 (바닥탈출 시도)": "a02",
    "✅ 매수 (상승 추세 지속)": "a03",
    "📉 찐바닥 포착 (매수 대기)": "a04",
    "📉 매도 (추세이탈)": "b01",
    "⚠️ 매도 주의 (반등 끝자락)": "b02",
    "⚠️ 관망 (단기 고점 의심)": "b03",
    "↔️ 기술적 반등 (저항주의)": "c01",
    "↔️ 방향 탐색 중": "c02",
    "📉 기술적 반등 시도 (관망)": "c03",
    "📉 하락 추세 지속 (관망)": "c04",
    "Hold (관망)": "d01"
}

# --- [3. 분석 핵심 함수들] ---

def get_final_signal_with_code(rsi, hist_up, macd_cross, obv_confirmed, curr_p, s5, s5_prev, s20, s120, stoch_k, stoch_d, stoch_cross):
    """지표를 받아 텍스트 신호와 공통 코드(a01 등)를 동시에 반환"""
    final_signal = "Hold (관망)"
    
    s5_up = s5 > s5_prev
    is_bull_market = (curr_p > s120) or (s20 > s120)
    stoch_buy_trigger = stoch_cross and (stoch_k < 40)

    if s5 > s20:
        if s5_up:
            if hist_up and obv_confirmed:
                if (macd_cross or stoch_buy_trigger) and rsi < 70:
                    final_signal = "🔥 강력 매수 (완벽한 눌림목 타점)" if is_bull_market else "✅ 매수 (바닥탈출 시도)"
                else:
                    final_signal = "✅ 매수 (상승 추세 지속)" if is_bull_market else "↔️ 기술적 반등 (저항주의)"
            else:
                final_signal = "↔️ 방향 탐색 중"
        else:
            final_signal = "⚠️ 관망 (단기 고점 의심)" if is_bull_market else "⚠️ 매도 주의 (반등 끝자락)"
    else:
        if s5_up:
            if (macd_cross or stoch_buy_trigger) and hist_up and rsi < 40:
                final_signal = "📉 찐바닥 포착 (매수 대기)"
            else:
                final_signal = "📉 기술적 반등 시도 (관망)"
        else:
            if curr_p < s5 and not is_bull_market:
                final_signal = "📉 매도 (추세이탈)"
            else:
                final_signal = "📉 하락 추세 지속 (관망)"

    return final_signal, SIGNAL_MAP.get(final_signal, "d01")

def analyze_candle_pattern(open_p, high_p, low_p, close_p, prev_close):
    candle_length = high_p - low_p
    if candle_length == 0:
        return 'gray', 'p04', '도지/단봉 (관망)'

    body = abs(close_p - open_p)
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p

    if (body / candle_length) < 0.1:
        return 'gray', 'p04', '도지/단봉 (관망)'

    if close_p > open_p:
        if lower_shadow > body * 1.5: 
            return 'green', 'p01', '망치형 (매수세 강함)'
        elif upper_shadow > body * 1.5: 
            return 'orange', 'p03', '역망치형 (매물 출회)'
        else:
            is_long = body > prev_close * 0.05
            return ('green', 'p07', '장대양봉') if is_long else ('orange', 'p02', '단봉(양)')
    else:
        if upper_shadow > body * 1.5: 
            return 'red', 'p06', '유성형 (하락 반전)'
        elif lower_shadow > body * 1.5: 
            return 'orange', 'p08', '교수형 (지지 확인)'
        else:
            is_long = body > prev_close * 0.05
            return ('red', 'p09', '장대음봉') if is_long else ('orange', 'p05', '단봉(음)')

# --- [4. 보조 지표 계산 함수] ---
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

# --- [5. 🚀 핵심: 배열(Batch) 처리 함수] ---

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

            # C 신호등 및 캔들 패턴
            c_signal, p_code, p_name = analyze_candle_pattern(
                df['Open'].iloc[-1], df['High'].iloc[-1], df['Low'].iloc[-1], close_p, df['Close'].iloc[-2]
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

def get_category_briefing(category_name, stock_data_list):
    """Gemini AI를 사용한 카테고리별 요약 생성"""
    context = "\n".join([f"- {s['name']} (${s['price']}): {s['signal']}" for s in stock_data_list])
    prompt = f"당신은 금융 분석가입니다. 아래 데이터를 요약하세요.\n{context}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {'Content-Type': 'application/json'}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-flash-preview:generateContent?key={GEMINI_API_KEY}"
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return "AI 요약을 생성할 수 없습니다."
