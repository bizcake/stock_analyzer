import pandas as pd
import numpy as np
import os
from decimal import Decimal
from django.db import transaction
import pytz
from datetime import datetime, timedelta
from stock.models import StockMaster, StockDailyChart, StockAnalysisLatest2
from .sync_stock import sync_intraday_today
from .indicators import (
    calc_wavetrend, calc_macd, calc_rsi, calc_supertrend,
    calc_adx, calc_mfi, calc_obv, calc_atr, calc_squeeze,
    calc_candle_pattern, get_signal_priority,
    calc_t_signal, calc_n_signal, calc_up_days,
)

MIN_DAYS = 120  # 분석 최소 데이터 수

# 1. 환경 분리: 구글 클라우드 환경인지 확인
IS_CLOUD_RUN = os.environ.get('K_SERVICE') is not None

def _load_df(ticker: str) -> pd.DataFrame | None:
    """DB에서 종목 차트 데이터 로드 → DataFrame"""
    rows = (
        StockDailyChart.objects
        .filter(stock_id=ticker)
        .order_by('date')
        .values('date', 'open_price', 'high_price',
                'low_price', 'close_price', 'adj_close', 'volume')
    )
    if not rows:
        return None

    df = pd.DataFrame(list(rows))
    for col in ['open_price', 'high_price', 'low_price', 'close_price', 'adj_close']:
        df[col] = df[col].astype(float)
    df['volume'] = df['volume'].astype(float)

    # indicators.py 함수들이 High/Low/Close/Open/Volume 컬럼명 사용
    df = df.rename(columns={
        'open_price':  'Open',
        'high_price':  'High',
        'low_price':   'Low',
        'close_price': 'Close',
        'adj_close':   'Adj Close',
        'volume':      'Volume',
    })
    return df.reset_index(drop=True)


def _analyze_one(ticker: str, df: pd.DataFrame) -> dict | None:
    """종목 하나 분석 → 저장용 dict 반환"""
    try:
        close   = df['Close']
        close_p = float(close.iloc[-1])

        # ── 지표 계산 ────────────────────────────
        wt1, wt2           = calc_wavetrend(df)
        macd, macd_sig     = calc_macd(close)
        macd_hist          = macd - macd_sig
        rsi                = float(calc_rsi(close).iloc[-1])
        st_dir, st_val     = calc_supertrend(df)
        adx                = calc_adx(df)
        mfi                = calc_mfi(df)
        obv, obv_confirmed = calc_obv(df)
        atr14              = calc_atr(df)
        sq                 = calc_squeeze(df, wt1, wt2)

        # ── 시그널 ───────────────────────────────
        sig = get_signal_priority(st_dir, wt1, wt2, obv_confirmed, sq)

        # ── 신호등 ───────────────────────────────
        t_signal = calc_t_signal(df, wt1, wt2)
        n_signal = calc_n_signal(df, close_p, macd, macd_sig, obv)

        # ── 캔들 패턴 ────────────────────────────
        c_signal, p_code, p_name = calc_candle_pattern(
            float(df['Open'].iloc[-1]),
            float(df['High'].iloc[-1]),
            float(df['Low'].iloc[-1]),
            close_p,
            float(close.iloc[-2]),
            atr14,
        )

        # ── 이동평균 ─────────────────────────────
        sma5   = float(close.rolling(5).mean().iloc[-1])
        sma20  = float(close.rolling(20).mean().iloc[-1])
        sma120 = float(close.rolling(120).mean().iloc[-1])
        deviation = (close_p - sma20) / sma20 * 100 if sma20 else 0

        # ── 거래량 ───────────────────────────────
        vol_curr  = float(df['Volume'].iloc[-1])
        vol_ma20  = sq['vol_ma20']
        vol_ratio = round(vol_curr / vol_ma20, 2) if vol_ma20 > 0 else 0

        # ── 등락률 ───────────────────────────────
        prev_close  = float(close.iloc[-2])
        change_rate = round((close_p - prev_close) / prev_close * 100, 2) \
                      if prev_close else 0

        # ── 연속 상승일 ──────────────────────────
        up_days = calc_up_days(close)

        return {
            'analyzed_date':       df['date'].iloc[-1] if 'date' in df.columns \
                                   else None,
            'close_price':         Decimal(str(round(close_p, 4))),
            'volume':              int(vol_curr),
            'vol_ratio':           vol_ratio,
            'change_rate':         change_rate,
            't_signal':            t_signal,
            'n_signal':            n_signal,
            'c_signal':            c_signal,
            'p_code':              p_code,
            'p_name':              p_name,
            'up_days':             up_days,
            'signal_code_id':      sig['signal_code'],  # FK
            'signal':              sig['signal'],
            'priority':            sig['priority'],
            'action':              sig['action'],
            'supertrend_direction':st_dir,
            'supertrend_value':    Decimal(str(round(st_val, 4))),
            'wt1':                 sig['wt1'],
            'wt2':                 sig['wt2'],
            'wt_cross_up':         sig['wt_cross_up'],
            'wt_cross_down':       sig['wt_cross_down'],
            'wt_oversold':         sig['wt_oversold'],
            'wt_overbought':       sig['wt_overbought'],
            'wt_momentum':         sig['wt_momentum'],
            'is_squeeze':          sq['is_squeeze'],
            'squeeze_released':    sq['squeeze_released'],
            'obv_confirmed':       obv_confirmed,
            'rsi':                 round(rsi, 2),
            'macd':                round(float(macd.iloc[-1]), 4),
            'macd_signal':         round(float(macd_sig.iloc[-1]), 4),
            'macd_hist':           round(float(macd_hist.iloc[-1]), 4),
            'adx':                 round(adx, 2),
            'mfi':                 round(mfi, 2),
            'sma5':                round(sma5, 4),
            'sma20':               round(sma20, 4),
            'sma120':              round(sma120, 4),
            'deviation':           round(deviation, 2),
        }

    except Exception as e:
        print(f"  [{ticker}] 분석 오류: {e}")
        return None

def analyze_batch_signals(tickers=None, chunk_size=500):
    """
    DB 차트 데이터 → 분석 → StockAnalysisLatest2 저장

    tickers   : None = 전체, list = 해당 종목만
    chunk_size : bulk_create 단위
    """
    print("📊 분석 시작...")

    qs = StockMaster.objects.all()
    if tickers:
        qs = qs.filter(ticker__in=tickers)
    ticker_list = list(qs.values_list('ticker', flat=True))
    total       = len(ticker_list)
    print(f"대상 종목: {total}개")

    success, fail, skip = 0, 0, 0
    objects = []

    UPDATE_FIELDS = [
        'analyzed_date', 'close_price', 'volume', 'vol_ratio', 'change_rate',
        't_signal', 'n_signal', 'c_signal', 'p_code', 'p_name', 'up_days',
        'signal_code_id', 'signal', 'priority', 'action',
        'supertrend_direction', 'supertrend_value',
        'wt1', 'wt2', 'wt_cross_up', 'wt_cross_down',
        'wt_oversold', 'wt_overbought', 'wt_momentum',
        'is_squeeze', 'squeeze_released', 'obv_confirmed',
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'adx', 'mfi', 'sma5', 'sma20', 'sma120', 'deviation',
        'updated_at',
    ]

    for idx, ticker in enumerate(ticker_list, 1):
        try:
            df = _load_df(ticker)

            if df is None or len(df) < MIN_DAYS:
                days = len(df) if df is not None else 0
                print(f"[{idx}/{total}] {ticker} 데이터 부족({days}일) → 스킵")
                skip += 1
                continue

            data = _analyze_one(ticker, df)
            if data is None:
                fail += 1
                continue

            objects.append(StockAnalysisLatest2(stock_id=ticker, **data))
            success += 1

            # chunk 단위 저장
            if len(objects) >= chunk_size:
                _bulk_upsert(objects, UPDATE_FIELDS)
                objects = []
                print(f"[{idx}/{total}] {chunk_size}건 저장 완료...")

        except Exception as e:
            print(f"[{idx}/{total}] {ticker} 오류: {e}")
            fail += 1

    # 잔여 저장
    if objects:
        _bulk_upsert(objects, UPDATE_FIELDS)

    print(f"\n✅ 완료 — 성공: {success} / 스킵: {skip} / 실패: {fail}")
    return {'success': success, 'skip': skip, 'fail': fail}


def _bulk_upsert(objects, update_fields):
    with transaction.atomic():
        StockAnalysisLatest2.objects.bulk_create(
            objects,
            update_conflicts=True,
            unique_fields=['stock'],
            update_fields=update_fields,
        )


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
            if 8 <= hour <= 20:
                markets.append('KR')
                
            # 미국 시장: 23시 ~ 07시 (서머타임 미고려 시 기준, 필요 시 조정 가능)
            if hour >= 21 or hour <= 8:
                markets.append('US')
        
        if IS_CLOUD_RUN == False:
            markets = []
            markets.append('US')
            # markets.append('KR')
        return markets, now.date()

    @classmethod
    def run_analysis(cls):
        """전체 분석 프로세스 실행"""
        target_markets, today_date = cls.get_target_markets()

        # 데이터 수집
        sync_intraday_today(batch_size=160, batch_delay=3.0, target_markets=target_markets)

        index_list = set(StockMaster.objects.filter(
            market__in=target_markets,
            index_type__isnull=False  # 🚀 여기가 필터링의 핵심입니다!
        ).values_list('ticker', flat=True))

        all_tickers = list(index_list)
        # 주식 분석
        analyze_batch_signals(tickers=all_tickers)
