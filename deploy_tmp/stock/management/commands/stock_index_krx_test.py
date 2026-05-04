from pykrx import stock
from pykrx import stock as krx_stock

import pandas as pd
from datetime import datetime, timedelta

# 가장 기초적인 시장 리스트 가져오기 테스트
# markets = stock.get_market_ticker_list(market="KOSPI")

for i in range(100):
    target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
    codes = krx_stock.get_index_portfolio_deposit_file("1028", date=target_date)
    print(codes)
    # if codes:
    #     print(f"✅ 접속 성공! 코스피 종목 수: {len(codes)}개")
    # else:
    #     print("❌ 접속은 되었으나 데이터를 가져오지 못했습니다. (IP 차단 의심)")