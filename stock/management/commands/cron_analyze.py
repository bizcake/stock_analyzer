
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from stock.services import StockAnalyzerService
from stock.models import StockAnalysisHistory

class Command(BaseCommand):
    help = 'Run stock market analysis for configured markets and save to DB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--market',
            type=str,
            help='Filter by market (KR, US, COIN)',
            default=None
        )

    def handle(self, *args, **options):
        try:
            market = options.get('market')
            
            self.stdout.write(f"🚀 분석 시작... (마켓: {market or '전체'})")
            
            success_count = StockAnalyzerService.run_analysis(market=market)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ 분석 완료. 총 {success_count}개 종목이 처리되었습니다.')
            )

            # 오래된 히스토리 정리 (6개월 전 데이터 삭제)
            today_date = timezone.now().date()
            six_months_ago = today_date - timedelta(days=180)
            deleted_count, _ = StockAnalysisHistory.objects.filter(date__lt=six_months_ago).delete()
            if deleted_count > 0:
                self.stdout.write(f"🧹 {deleted_count}개의 오래된 히스토리 데이터를 정리했습니다.")

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'❌ 분석 실패: {str(e)}')
            )
            raise
