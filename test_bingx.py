import requests
import pandas as pd
import json

BINGX_BASE = "https://open-api.bingx.com"

def test_bingx_api():
    symbol = "BTC-USDT"
    interval = "1h"
    limit = 5
    
    url = f"{BINGX_BASE}/openApi/swap/v3/quote/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
    }
    
    print(f"Calling BingX API: {url} with params {params}")
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    
    if data.get('code') != 0:
        print(f"Error: {data}")
        return

    rows = data['data']
    print(f"\nRaw first row: {rows[0]}")
    print(f"Number of columns in response: {len(rows[0])}")
    
    # 현재 코드의 매핑 방식
    columns=[
        'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ]
    
    df = pd.DataFrame(rows, columns=columns)
    print("\nDataFrame Head:")
    print(df)
    
    print("\nData Types:")
    print(df.dtypes)

if __name__ == "__main__":
    test_bingx_api()
