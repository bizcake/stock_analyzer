# stock/management/commands/load_coins.py
from django.core.management.base import BaseCommand
from stock.models import StockMaster

class Command(BaseCommand):
    help = "주요 코인 데이터를 StockMaster에 등록합니다."

    def handle(self, *args, **options):
        # 분석 대상에 포함될 주요 코인 리스트 (야후 파이낸스 티커 기준)
        coins = [
            {'ticker': 'BTC-USD', 'name': '비트코인'},
            {'ticker': 'ETH-USD', 'name': '이더리움'},
            {'ticker': 'SOL-USD', 'name': '솔라나'},
            {'ticker': 'XRP-USD', 'name': '리플'},
            {'ticker': 'DOGE-USD', 'name': '도지코인'},
        ]

        count = 0
        for coin in coins:
            # index_type을 'COIN'으로 설정하여 분석 엔진이 인식하게 함
            obj, created = StockMaster.objects.update_or_create(
                ticker=coin['ticker'],
                defaults={
                    'name_kr': coin['name'],
                    'market': 'COIN',
                    'index_type': 'COIN' 
                }
            )
            if created:
                count += 1

        self.stdout.write(f"✅ {count}개의 코인이 새로 등록되었습니다.")