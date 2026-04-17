import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from ..stock.models import MyTrackedStock, StockAnalysisLatest

load_dotenv()  # .env 파일 로드

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    """텔레그램 메시지 발송 함수"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("텔레그램 토큰이 설정되지 않았습니다.")
        return
        
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

def send_analysis_alert(market_name):
    """DB의 최신 분석 결과를 읽어 유의미한 시그널만 발송"""
    # 강력 매수(a01, a02 등), 또는 매도(b01, b02 등) 코드를 필터링
    target_codes = ['a01', 'a02', 'a03', 'a04', 'b01', 'b02', 'c03', 'c04']
    
    # 내 관심종목 중 해당 시그널 코드를 가진 종목만 추출
    picks = MyTrackedStock.objects.filter(
        stock__market=market_name,
        stock__latest_analysis__signal_code__in=target_codes
    ).select_related('stock', 'stock__latest_analysis')
    
    picks_text = []
    for item in picks:
        analysis = item.stock.latest_analysis
        if analysis:
            formatted_txt = (
                f"• <b>{item.stock.name_kr}</b> ({item.stock.ticker})\n"
                f"  ↳ 패턴: {analysis.p_name}\n"
                f"  ↳ 코드: {analysis.signal_code}"
            )
            picks_text.append(formatted_txt)

    if not picks_text:
        msg = "💡 <b>[시장 시그널 알림]</b>\n현재 새롭게 포착된 유의미한 시그널(매수/매도)이 없습니다."
    else:
        msg = "🚀 <b>[주요 시그널 포착 알림]</b>\n\n"
        msg += f"📊 <b>[{market_name}] 마켓</b>\n"
        msg += "\n\n".join(picks_text) + "\n\n"
        
    send_telegram_message(msg)