import os
import time
import requests
import schedule
from datetime import datetime
import pytz

# 기존에 잘 만들어둔 스캐너 모듈 임포트
from utils import get_signals_batch

from dotenv import load_dotenv


load_dotenv()  # .env 파일 로드

# ==========================================
# [추가] 실행 시 자신의 PID를 파일에 기록
# ==========================================
PID_FILE = "bot.pid"
with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))
print(f"🤖 봇 프로세스 시작됨 (PID: {os.getpid()})")

# 기존에 잘 만들어둔 스캐너 모듈 임포트

# ==========================================
# 1. 텔레그램 및 알림 설정
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ==========================================
# 2. 코스피 100 & 나스닥 100 종목 리스트 (딕셔너리 형태)
# ==========================================
# (예시로 몇 개만 넣었습니다. 여기에 100개씩 채워넣으시면 됩니다.)
TARGET_STOCKS = {
    "KOSPI": {
        # --- 반도체/전자 ---
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005935.KS": "삼성전자우", "066570.KS": "LG전자",
        "009150.KS": "삼성전기", "000990.KS": "DB하이텍", "011070.KS": "LG이노텍", "034220.KS": "LG디스플레이",
        "042700.KS": "한미반도체", "006400.KS": "삼성SDI", "018260.KS": "삼성에스디에스",
        "003550.KS": "LG", "034730.KS": "SK", "000880.KS": "한화", "010120.KS": "LS일렉트릭",
        "006260.KS": "LS", "011170.KS": "롯데케미칼", "011780.KS": "금호석유", "010950.KS": "S-Oil",

        # --- 자동차/조선/기계 ---
        "005380.KS": "현대차", "000270.KS": "기아", "012330.KS": "현대모비스", "086280.KS": "현대글로비스",
        "012450.KS": "한화에어로스페이스", "042660.KS": "한화오션", "009540.KS": "HD한국조선해양",
        # "010620.KS": "HD현대미포", <-- 야후 API 오류로 임시 제외
        "034020.KS": "두산에너빌리티", "000150.KS": "두산", "021240.KS": "코웨이", "004020.KS": "현대제철",
        "005490.KS": "POSCO홀딩스", "003670.KS": "포스코퓨처엠", "047050.KS": "포스코인터내셔널", "001040.KS": "CJ",
        "000120.KS": "CJ대한통운", "097950.KS": "CJ제일제당", "003490.KS": "대한항공",

        # --- 금융/지주 ---
        "000810.KS": "삼성화재", "005830.KS": "DB손해보험", "001450.KS": "현대해상", "138040.KS": "메리츠금융지주",
        "071050.KS": "한국금융지주", "005940.KS": "NH투자증권", "138930.KS": "BNK금융지주", "175330.KS": "JB금융지주",
        "316140.KS": "우리금융지주", "105560.KS": "KB금융", "055550.KS": "신한지주", "086790.KS": "하나금융지주",
        "088350.KS": "한화생명", "024110.KS": "기업은행", "323410.KS": "카카오뱅크", "377300.KS": "카카오페이",

        # --- 기타 주요 종목 및 이전 상장 종목 ---
        "000100.KS": "유한양행", "000210.KS": "DL", "000240.KS": "한국앤컴퍼니",
        "000720.KS": "현대건설", "001430.KS": "세아베스틸지주", "001740.KS": "SK네트웍스", "002380.KS": "KCC",
        "030000.KS": "제일기획", "004170.KS": "신세계", "004370.KS": "농심", "004990.KS": "롯데지주",
        "005300.KS": "롯데칠성", "006360.KS": "GS건설", "007070.KS": "GS리테일", "008770.KS": "호텔신라",
        "008930.KS": "한미사이언스", "009830.KS": "한화솔루션", "010060.KS": "OCI홀딩스",
        "010130.KS": "고려아연", "011200.KS": "HMM", "011790.KS": "SKC", "016360.KS": "삼성증권",
        "017670.KS": "SK텔레콤", "020000.KS": "한섬", "023530.KS": "롯데쇼핑",
        "028260.KS": "삼성물산", "030200.KS": "KT", "032640.KS": "LG유플러스",
        "033780.KS": "KT&G", "035420.KS": "NAVER", "035720.KS": "카카오", "036460.KS": "한국가스공사",
        "036570.KS": "엔씨소프트", "051900.KS": "LG생활건강", "051910.KS": "LG화학",
        "068270.KS": "셀트리온", "069620.KS": "대웅제약", "078930.KS": "GS",
        "090430.KS": "아모레퍼시픽", "096770.KS": "SK이노베이션", "128940.KS": "한미약품",
        "139480.KS": "이마트", "161390.KS": "한국타이어앤테크놀로지", "180640.KS": "한진칼", "207940.KS": "삼성바이오로직스",
        "251270.KS": "넷마블", "267250.KS": "HD현대", "271560.KS": "오리온", "302440.KS": "SK바이오사이언스",
        "329180.KS": "HD현대중공업", "352820.KS": "하이브", "361610.KS": "SK아이이테크놀로지",
        "373220.KS": "LG에너지솔루션", "402340.KS": "SK스퀘어", "450080.KS": "에코프로머티",
        "034230.KS": "파라다이스", "066970.KS": "엘앤에프", "030190.KS": "NICE평가정보" # <-- 코스피 이전 상장 반영
    },
    "KOSDAQ": {
        # --- 이차전지/반도체/바이오 상위 ---
        "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로", "291230.KQ": "엔켐",
        "078600.KQ": "대주전자재료", "058470.KQ": "리노공업", "039030.KQ": "이오테크닉스", "067310.KQ": "하나마이크론",
        "032500.KQ": "케이엠더블유", "022220.KQ": "알체라", "121600.KQ": "나노신소재",
        "214150.KQ": "클래시스", "145020.KQ": "휴젤", "068760.KQ": "셀트리온제약", "214370.KQ": "케어젠",
        "036830.KQ": "솔브레인", "066910.KQ": "메디톡스", "086900.KQ": "메디포스트", "053030.KQ": "바이넥스",
        "263750.KQ": "펄어비스", "293490.KQ": "카카오게임즈", "112040.KQ": "위메이드", "253450.KQ": "스튜디오드래곤",
        "041510.KQ": "에스엠", "035900.KQ": "JYP Ent.", "122870.KQ": "와이지엔터테인먼트",
        "003380.KQ": "하림지주", "054920.KQ": "상신브레이크",
        "060250.KQ": "NHNKCP", "067160.KQ": "SOOP", "035760.KQ": "CJ ENM",
        "028300.KQ": "에이치엘비", "036930.KQ": "주성엔지니어링", "005290.KQ": "동진쎄미켐", "033640.KQ": "네패스",
        "084370.KQ": "유진테크", "036200.KQ": "유니테스트", "064550.KQ": "바이오니아", "025900.KQ": "동화기업",
        "035600.KQ": "KG이니시스", "035080.KQ": "인터로조", "053800.KQ": "안랩",
        "065350.KQ": "신성델타테크", "196170.KQ": "알테오젠", "203400.KQ": "네오위즈", "237690.KQ": "에스티팜"
    },
    "NASDAQ": {
        # --- 빅테크 및 반도체 ---
        "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "구글A", "GOOG": "구글C",
        "AMZN": "아마존", "NVDA": "엔비디아", "META": "메타", "TSLA": "테슬라",
        "AVGO": "브로드컴", "COST": "코스트코", "PEP": "펩시코", "ADBE": "어도비",
        "CSCO": "시스코", "NFLX": "넷플릭스", "AMD": "AMD", "TMUS": "티모바일",
        "INTC": "인텔", "QCOM": "퀄컴", "TXN": "텍사스인스트루먼트", "AMAT": "어플라이드머티어리얼즈",
        "ISRG": "인튜이티브서지컬", "SBUX": "스타벅스", "BKNG": "부킹홀딩스", "GILD": "길리어드",
        "MDLZ": "몬델리즈", "VRTX": "버텍스", "ADP": "ADP", "REGN": "리제네론",
        "ADI": "아날로그디바이스", "LRCX": "램리서치", "KLAC": "KLA", "PANW": "팔로알토",
        "SNPS": "시놉시스", "CDNS": "케이던스", "ASML": "ASML", "PYPL": "페이팔",
        "MAR": "메리어트", "ABNB": "에어비앤비", "ORLY": "오라일리", "MNST": "몬스터베버리지",
        "CTAS": "신타스", "WDAY": "워크데이", "PCAR": "파카", "PAYX": "페이첵스",
        "ROST": "로스스토어", "ADSK": "오토데스크", "AEP": "아메리칸일렉트릭", "KDP": "큐리그닥터페퍼",
        "AZN": "아스트라제네카", "TEAM": "아틀라시안", "IDXX": "아이덱스", "CPRT": "코파트",

        # --- 주요 기술주 및 성장주 ---
        "MCHP": "마이크로칩", "KHC": "크래프트헤인즈", "BKR": "베이커휴즈", "CHTR": "차터커뮤니케이션",
        "ON": "온세미", "MRVL": "마벨테크놀로지", "EXC": "엑셀론", "FAST": "파스날",
        "DDOG": "데이터독", "ODFL": "올드도미니언", "CTSH": "코그니전트", "CSGP": "코스타그룹",
        "EA": "일렉트로닉아츠", "GEHC": "GE헬스케어", "BIIB": "바이오젠", "DXCM": "덱스콤",
        "WBD": "워너브라더스", "ILMN": "일루미나", "ZS": "지스케일러", "DLTR": "달러트리",
        "GFS": "글로벌파운드리", "CEG": "컨스텔레이션", "MDB": "몽고DB",
        "VRSK": "베리스크", "ALNY": "앨나일람", "TTWO": "테이크투", "FTNT": "포티넷",
        "ENPH": "엔페이즈", "FANG": "다이아몬드백", "ALGN": "얼라인",
        "EBAY": "이베이", "LCID": "루시드", "APP": "앱러빈",
        "ARM": "암홀딩스", "PLTR": "팔란티어", "MSTR": "마이크로스트레티지", "MELI": "메르카도리브레"
    }
}

def send_telegram_message(text):
    """텔레그램 메시지 발송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
        print(f"[{datetime.now()}] 텔레그램 발송 성공")
    except Exception as e:
        print(f"텔레그램 발송 실패: {e}")

def run_market_scan():
    """종목 스캔 및 알림 필터링 핵심 로직"""
    print("\n===========================================")
    print(f"🚀 스케줄 스캔 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 티커 리스트 병합
    all_tickers = list(TARGET_STOCKS["KOSPI"].keys()) + list(TARGET_STOCKS["KOSDAQ"].keys()) + list(TARGET_STOCKS["NASDAQ"].keys())

    # 2. 50개씩 나눠서 배치 스캔
    results = get_signals_batch(all_tickers, chunk_size=50)

    kospi_picks = []
    kosdaq_picks = [] # 기존 코드에 누락되었던 코스닥 리스트 추가
    nasdaq_picks = []

    # 3. 조건 필터링 및 텍스트 조립
    for ticker, data in results.items():
        signal = data.get('signal', '')

        # [조건 완화] '관망' 또는 '데이터 부족'이 아닌 모든 유의미한 시그널(매수/매도/추세이탈 등) 알림
        if "관망" not in signal and "데이터 부족" not in signal:

            # 종목명 및 소속 시장 정확히 매핑 (코스닥 누락 버그 픽스)
            if ticker in TARGET_STOCKS["KOSPI"]:
                name = TARGET_STOCKS["KOSPI"][ticker]
                market = "KOSPI"
            elif ticker in TARGET_STOCKS["KOSDAQ"]:
                name = TARGET_STOCKS["KOSDAQ"][ticker]
                market = "KOSDAQ"
            else:
                name = TARGET_STOCKS["NASDAQ"].get(ticker, ticker)
                market = "NASDAQ"

            # 슈퍼트렌드 라벨 추출 (딕셔너리 구조 대응)
            st_dict = data.get('supertrend', {})
            st_label = st_dict.get('label', '')
            if not st_label: # 혹시 스캐너 반환 포맷이 다를 경우를 대비한 안전 장치
                trend_dir = data.get('trend_direction', 0)
                trend_count = data.get('trend_count', 0)
                st_label = f"{'상승' if trend_dir == 1 else '하락'} {trend_count}일째"

            # 트레이딩뷰 다이렉트 링크 생성
            if ".KS" in ticker:
                tv_symbol = f"KRX:{ticker.replace('.KS', '')}"
            elif ".KQ" in ticker:
                tv_symbol = f"KRX:{ticker.replace('.KQ', '')}"
            else:
                tv_symbol = ticker # 미국 주식

            chart_url = f"https://kr.tradingview.com/chart/?symbol={tv_symbol}"

            # 모바일 가독성을 고려한 줄바꿈 포맷팅 (링크 포함)
            formatted_txt = (
                f"• <b>{name}</b> ({ticker})\n"
                f"  ↳ 신호: {signal}\n"
                f"  ↳ 추세: <a href='{chart_url}'><b>[{st_label}]</b></a>"
            )

            if market == "KOSPI":
                kospi_picks.append(formatted_txt)
            elif market == "KOSDAQ":
                kosdaq_picks.append(formatted_txt)
            else:
                nasdaq_picks.append(formatted_txt)

    # 4. 텔레그램 메시지 조립
    if not kospi_picks and not kosdaq_picks and not nasdaq_picks:
        msg = "💡 <b>[시장 시그널 알림]</b>\n현재 새롭게 포착된 유의미한 시그널(매수/매도)이 없습니다."
    else:
        msg = "🚀 <b>[주요 시그널 포착 알림]</b>\n\n"

        if kospi_picks:
            msg += "🇰🇷 <b>[KOSPI]</b>\n"
            msg += "\n\n".join(kospi_picks) + "\n\n"

        if kosdaq_picks:
            msg += "🇰🇷 <b>[KOSDAQ]</b>\n"
            msg += "\n\n".join(kosdaq_picks) + "\n\n"

        if nasdaq_picks:
            msg += "🇺🇸 <b>[NASDAQ]</b>\n"
            msg += "\n\n".join(nasdaq_picks)

    # 5. 전송
    send_telegram_message(msg)
    print("🚀 스캔 및 발송 완료")

# ==========================================
# 3. 스케줄러 등록 및 실행 (한국 시간 기준)
# ==========================================
def job():
    run_market_scan()

if __name__ == "__main__":
    print("🤖 텔레그램 스캐너 봇이 시작되었습니다.")

    # 만약 서버(PythonAnywhere 등)가 UTC 기준이라면 시간을 조정해야 합니다.
    # 한국 시간(KST) 08:30 = UTC 23:30 (전날)
    # 아래 설정은 "실행되는 서버의 로컬 시간" 기준입니다.

    schedule.every().day.at("08:30").do(job)
    schedule.every().day.at("13:30").do(job)
    schedule.every().day.at("20:30").do(job)

    # (테스트용) 스크립트 실행 시 즉시 한 번 발송해보고 싶다면 아래 주석을 해제하세요.
    run_market_scan()

    while True:
        schedule.run_pending()
        time.sleep(30) # 30초마다 스케줄 확인