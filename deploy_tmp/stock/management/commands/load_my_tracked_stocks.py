from django.core.management.base import BaseCommand
from stock.models import StockMaster, MyTrackedStock

class Command(BaseCommand):
    help = "제공된 리스트를 StockMaster에 확인 후 MyTrackedStock 테이블에 일괄 등록합니다."

    def handle(self, *args, **options):
        # 1. 입력 데이터
        target_data = {
            "코인": {
                "리플(XRP)": "XRP-USD", "비트코인(BTC)": "BTC-USD", "이더리움(ETH)": "ETH-USD",
                "솔라나(SOL)": "SOL-USD", "페페": "PEPE24478-USD", "도지코인": "DOGE-USD"
            },
            "해외": {
                "힘스 허스 핼스": "HIMS", "나스닥100": "QQQ", "반도체": "SMH", "루멘텀홀딩스": "LITE",
                "테슬라 2배(TSLL)": "TSLL", "코인베이스 2배(CONL)": "CONL", "J.P.모건 JEPQ": "JEPQ",
                "서클 2배(CRCA)": "CRCA", "사이더스 스페이스(SIDU)": "SIDU", "레드와이어(RDW)": "RDW",
                "리게티 컴퓨팅(RGTI)": "RGTI", "넷스코프": "NTSK", "아이렌(IREN)": "IREN",
                "파이어플라이 에어로스페이스(FLY)": "FLY", "아크 혁신(ARQ)": "ARQ", "비트코인 2배(BITU)": "BITU",
                "XTI 에어로스페이스": "XTIA", "마이크로스트레티지": "MSTR", "파가야(PGY)": "PGY",
                "스카이워터 테크놀로지스": "SKYT", "제타 글로벌(ZETA)": "ZETA", "항셍테크(KTEC)": "KTEC",
                "조비 에비에이션(JOBY)": "JOBY", "엔비디아(NVDA)": "NVDA", "소파이(SOFI)": "SOFI",
                "양자보안(QTUM)": "QTUM", "브렌트오일": "BNO", "스타벅스": "SBUX", "뉴스케일파워": "SMR",
                "로켓랩": "RKLB", "아이온큐": "IONQ", "테슬라": "TSLA", "슐렘버거": "SLB"
            },
            "국내": {
                "한화에어로스페이스": "012450.KS", "한화오션": "042660.KS", "이엠코리아": "095190.KQ",
                "롯데손해보": "000400.KS", "우리기술": "032820.KQ", "TIGER 차이나휴머노이드로봇": "0053L0.KS",
                "블루엠텍 ": "439580.KQ", "제룡전기": "033100.KQ", "안트로젠": "065660.KQ",
                "삼아알미늄": "006110.KS", "에스앤디": "260970.KQ", "테스": "095610.KQ",
                "로킷헬스케어": "376900.KQ", "이수페타시스": "007660.KS", "파마리서치": "214450.KQ",
                "카카오": "035720.KS", "대한전선": "001440.KS", "힌화비전": "489790.KS",
                "두산에너빌리티": "034020.KS", "제일일렉트릭": "199820.KQ", "영원무역": "111770.KS",
                "kodex고배당": "279530.KS", "POSCO홀딩스": "005490.KS", "LS그룹": "006260.KS",
                "현대건설": "000720.KS", "tiger 구리실물": "160580.KS", "tiger 반도체top10": "396500.KS",
                "kodex 2차전지산업": "305720.KS", "sk이터닉스": "475150.KS", "LS마린솔루션": "060370.KS",
                "kodex 코스닥 150": "229200.KS", "kodex 코스피200": "069500.KS"
            }
        }

        market_mapping = {"코인": "COIN", "해외": "US", "국내": "KR"}
        total_count = 0

        for category, stocks in target_data.items():
            market_code = market_mapping[category]
            for name, ticker in stocks.items():
                # 1. StockMaster에 있는지 먼저 확인 (없으면 생성)
                stock_master, created = StockMaster.objects.get_or_create(
                    ticker=ticker,
                    defaults={'name_kr': name.strip(), 'market': market_code}
                )

                # 2. MyTrackedStock에 등록
                # (중복 등록 방지를 위해 get_or_create 사용)
                tracked, is_new = MyTrackedStock.objects.get_or_create(stock=stock_master)

                if is_new:
                    total_count += 1
                    self.stdout.write(f"✅ MyTrackedStock 추가 완료: {name} ({ticker})")

        self.stdout.write(self.style.SUCCESS(f"\n🚀 총 {total_count}개의 종목이 내 관심종목(MyTrackedStock)에 추가되었습니다."))