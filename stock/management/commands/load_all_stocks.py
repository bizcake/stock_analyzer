# stock/management/commands/load_all_stocks.py
from django.core.management.base import BaseCommand
from stock.models import StockMaster
import FinanceDataReader as fdr

class Command(BaseCommand):
    help = "bulk_create를 사용하여 한국 및 미국 전체 종목을 초고속으로 로드합니다."

    def handle(self, *args, **options):
        self.stdout.write("🚀 데이터 수집 및 벌크 로드 시작...")

        # 1. 한국 시장 (KRX) 처리
        self.stdout.write("🇰🇷 한국 시장(KRX) 데이터를 가져오는 중...")
        df_krx = fdr.StockListing('KRX')
        
        kr_objects = []
        for _, row in df_krx.iterrows():
            code = str(row['Code'])
            market = str(row['Market'])
            name = str(row['Name'])
            
            # 티커 변환
            ticker = f"{code}.KS" if market == 'KOSPI' else f"{code}.KQ" if market == 'KOSDAQ' else None
            
            if ticker:
                kr_objects.append(StockMaster(
                    ticker=ticker,
                    name_kr=name,
                    market='KR'
                ))

        # 🚀 한국 주식 저장 (중복 시 무시하거나 업데이트)
        self.perform_bulk_upsert(kr_objects, "한국")

        # 2. 미국 시장 (NASDAQ, NYSE, AMEX) 처리
        us_markets = ['NASDAQ', 'NYSE', 'AMEX']
        for mkt in us_markets:
            self.stdout.write(f"🇺🇸 미국 시장({mkt}) 데이터를 가져오는 중...")
            df_us = fdr.StockListing(mkt)
            
            us_objects = [
                StockMaster(
                    ticker=str(row['Symbol']),
                    name_kr=str(row['Name']),
                    market='US'
                ) for _, row in df_us.iterrows()
            ]
            
            self.perform_bulk_upsert(us_objects, f"미국-{mkt}")

        self.stdout.write("🎉 모든 마스터 데이터 로드가 완료되었습니다.")

    def perform_bulk_upsert(self, objs, label):
        """
        Django 4.1+ 이상에서 지원하는 bulk_create의 update_conflicts 기능을 사용하여
        중복 티커는 이름을 업데이트하고, 없는 티커는 새로 생성합니다.
        """
        if not objs:
            return

        # bulk_create의 강력한 옵션들:
        # - update_conflicts=True: 중복 키 발생 시 에러 대신 업데이트 수행
        # - update_fields: 중복 시 업데이트할 필드 지정
        # - unique_fields: 중복 여부를 판단할 기준 필드 (ticker)
        
        StockMaster.objects.bulk_create(
            objs,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=['ticker'],
            update_fields=['name_kr'] # 이름이 바뀌었을 경우를 대비해 업데이트
        )
        self.stdout.write(f"   ✅ {label} 종목 {len(objs)}개 처리 완료 (Bulk)")