import os
import django
import FinanceDataReader as fdr
from pykrx import stock as k_stock # 국내 주식용 대체재
import pandas as pd

# 1. Django 환경 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stocks.settings')
django.setup()

from stock.models import StockMaster

def load_all_stocks():
    print("🚀 종목 데이터 수집 및 DB 적재 시작 (Hybrid Mode)")

    # --- [A] 국내 주식 (pykrx 사용 - 매우 안정적) ---
    for market_name, market_code in [('KOSPI', 'KOSPI'), ('KOSDAQ', 'KOSDAQ')]:
        print(f"📦 {market_name} 데이터 수집 중 (pykrx)...")
        try:
            # 티커 리스트 가져오기
            tickers = k_stock.get_market_ticker_list(market=market_code)
            suffix = ".KS" if market_name == 'KOSPI' else ".KQ"
            
            for ticker in tickers:
                name = k_stock.get_market_ticker_name(ticker)
                full_ticker = f"{ticker}{suffix}"
                
                StockMaster.objects.update_or_create(
                    ticker=full_ticker,
                    defaults={
                        'name_kr': name,
                        'market': market_name
                    }
                )
            print(f"✅ {market_name} 완료")
        except Exception as e:
            print(f"❌ {market_name} 오류: {e}")

    # --- [B] 미국 주식 (FDR 사용 - 최신 버전 필요) ---
    us_markets = [('NASDAQ', 'NASDAQ'), ('NYSE', 'NYSE'), ('AMEX', 'AMEX')]
    for market_name, fdr_code in us_markets:
        print(f"📦 {market_name} 데이터 수집 중 (FDR)...")
        try:
            # FDR이 내부적으로 인베스팅닷컴을 쓰는데, 에러가 잦을 경우 대비
            df = fdr.StockListing(fdr_code)
            
            for _, row in df.iterrows():
                ticker = str(row['Symbol']).strip()
                name = row['Name']
                
                StockMaster.objects.update_or_create(
                    ticker=ticker,
                    defaults={
                        'name_en': name,
                        'market': market_name
                    }
                )
            print(f"✅ {market_name} 완료")
        except Exception as e:
            print(f"❌ {market_name} 오류: {e}")
            print(f"💡 {market_name}의 경우 FDR 라이브러리 이슈일 수 있습니다. 'pip install -U finance-datareader'를 시도해보세요.")

    print("\n✨ 모든 작업이 완료되었습니다!")

if __name__ == "__main__":
    load_all_stocks()