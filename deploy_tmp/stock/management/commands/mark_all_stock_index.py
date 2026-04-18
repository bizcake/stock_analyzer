from django.core.management.base import BaseCommand
from stock.models import StockMaster
# from pykrx import stock as krx_stock
import FinanceDataReader as fdr

import pandas as pd
import requests
import io
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = "데이터가 있는 가장 최근 날짜를 자동으로 찾아 지수 정보를 업데이트합니다."

    def handle(self, *args, **options):
        # 1. 한국 지수 데이터 확보 (최근 10일간 루프 돌며 데이터 찾기)
        k200_list = set()
        q150_list = set()
        found_date = None

        # self.stdout.write("🔍 KRX 최신 지수 데이터를 찾는 중 (최대 10일 전까지 검색)...")
        
        try:
            # 1. 코스피 200 (네이버 금융 기준)
            # FDR의 StockListing('KOSPI')는 전체 목록이므로, 
            # KRX-MARCAP(시가총액 순)으로 상위 200개를 가져오는 방식으로 우회하거나
            # 별도의 외부 지수 리스트 URL을 활용해야 합니다.
            
            # 임시 방편: KRX 전체 종목 중 시가총액 상위 200개/150개를 가져옴
            df_krx = fdr.StockListing('KRX-MARCAP')
            
            # 코스피 종목 중 상위 200개
            k200_tickers = df_krx[df_krx['Market'] == 'KOSPI'].head(200)['Code'].tolist()
            k200_list = [f"{c}.KS" for c in k200_tickers]
            
            # 코스닥 종목 중 상위 150개
            q150_tickers = df_krx[df_krx['Market'] == 'KOSDAQ'].head(150)['Code'].tolist()
            q150_list = [f"{c}.KQ" for c in q150_tickers]
            
            self.stdout.write(f"✅ K200(추정): {len(k200_list)}개, Q150(추정): {len(q150_list)}개 확보")

            # 2. 나스닥 100 (기존 위키피디아 로직 유지 - 미국은 차단이 덜함)
            # ... (나스닥 로직 생략) ...

            # 3. DB 반영
            StockMaster.objects.update(index_type=None)
            StockMaster.objects.filter(ticker__in=k200_list).update(index_type='K200')
            StockMaster.objects.filter(ticker__in=q150_list).update(index_type='Q150')
            
            self.stdout.write("🎉 시가총액 기준으로 지수 정보가 업데이트되었습니다.")
            
        except Exception as e:
            self.stderr.write(f"❌ 실패: {e}")
            
        # for i in range(10):
        #     target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        #     try:
        #         # 코스피 200(1028) 시도
        #         codes = krx_stock.get_index_portfolio_deposit_file("1028", date=target_date)
                
        #         # 데이터가 존재하는지 체크 (리스트나 데이터프레임 모두 대응)
        #         is_empty = True
        #         if isinstance(codes, list):
        #             is_empty = len(codes) == 0
        #         elif hasattr(codes, 'empty'):
        #             is_empty = codes.empty
                
        #         if not is_empty:
        #             k200_list = set([f"{c}.KS" for c in codes])
        #             # 코스닥 150(2046)도 동일 날짜로 시도
        #             q_codes = krx_stock.get_index_portfolio_deposit_file("2046", date=target_date)
        #             q150_list = set([f"{c}.KQ" for c in q_codes])
                    
        #             found_date = target_date
        #             self.stdout.write(f"✅ {found_date} 날짜에서 한국 지수 데이터를 확보했습니다.")
        #             break # 데이터를 찾았으므로 루프 탈출
        #         else:
        #             self.stdout.write(f"   - {target_date}: 데이터 없음, 하루 전 시도 중...")
        #     except Exception:
        #         continue

        # --- 2. 나스닥 100 리스트 확보 (기존 로직 유지) ---
        n100_list = set()
        try:
            url = "https://en.wikipedia.org/wiki/Nasdaq-100"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers)
            tables = pd.read_html(io.StringIO(res.text))
            df_n100 = next((t for t in tables if 'Ticker' in t.columns), None)
            if df_n100 is not None:
                n100_list = set(df_n100['Ticker'].tolist())
                self.stdout.write(f"✅ NASDAQ 100 확보: {len(n100_list)}개")
        except Exception as e:
            self.stderr.write(f"⚠️ NASDAQ 100 실패: {e}")

        # --- 3. DB 업데이트 ---
        if k200_list or q150_list or n100_list:
            self.stdout.write("📝 DB 반영 중...")
            # 전체 종목의 지수 정보 초기화 (새로운 구성 반영을 위해)
            StockMaster.objects.update(index_type=None)

            if k200_list:
                updated = StockMaster.objects.filter(ticker__in=k200_list).update(index_type='K200')
                self.stdout.write(f"   - K200: {updated}개 매칭")
            if q150_list:
                updated = StockMaster.objects.filter(ticker__in=q150_list).update(index_type='Q150')
                self.stdout.write(f"   - Q150: {updated}개 매칭")
            if n100_list:
                updated = StockMaster.objects.filter(ticker__in=n100_list).update(index_type='N100')
                self.stdout.write(f"   - N100: {updated}개 매칭")
                
            self.stdout.write(f"🎉 모든 지수 업데이트가 완료되었습니다! (기준일: {found_date})")
        else:
            self.stderr.write("❌ 업데이트할 수 있는 데이터가 없습니다. 네트워크 상태나 API를 확인하세요.")