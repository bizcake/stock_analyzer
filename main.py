# main.py
import os
import django

# ⚠️ 'myproject.settings' 부분을 실제 settings.py가 있는 폴더 이름으로 변경하세요.
# 예: 폴더 이름이 config라면 'config.settings', stocks라면 'stocks.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stocks.settings') 
django.setup()
from analyzer.analyzer_service import MarketAnalyzerService as ServiceV1
from analyzer.analyzer_service2 import MarketAnalyzerService as ServiceV2
from analyzer.analyzer_service_coin import MarketAnalyzerService as ServiceCoin

# 3. [핵심] 실제 분석을 수행하는 내부 공통 함수
def _execute_all_analyses():
    print("🚀 전체 분석 시퀀스 시작")
    
    # V2 실행 (실패해도 V1에 영향을 주지 않음)
    try:
        print("➡️ 서비스 V2 실행 중...")
        ServiceV2.run_analysis()
    except Exception as e:
        print(f"❌ 서비스 V2 에러 발생: {e}")

    # V1 실행
    try:
        print("➡️ 서비스 V1 실행 중...")
        ServiceV1.run_analysis()
    except Exception as e:
        print(f"❌ 서비스 V1 에러 발생: {e}")
    
    # coin 실행
    try:
        print("➡️ 서비스 coin 실행 중...")
        ServiceCoin.run_analysis()
    except Exception as e:
        print(f"❌ 서비스 V1 에러 발생: {e}")
    
    print("✅ 모든 분석 시퀀스 종료")

def cloud_function_handler(event, context):
    _execute_all_analyses()
    return "Success"

# Cloud Functions의 Pub/Sub 트리거 기본 규격 (event, context)
def run_stock_analysis(event, context):
    print("클라우드 펑션 실행됨")
    _execute_all_analyses()
    return "Success"

# --- 로컬 테스트용 코드 ---
# 이 부분은 python main.py로 직접 실행할 때만 작동하며, GCP 배포 시에는 무시됩니다.
if __name__ == '__main__':
    print("🖥️ 로컬 환경에서 테스트를 시작합니다...")
    
    # 클라우드 Pub/Sub가 보낸다고 가정하는 가짜(Mock) 데이터
    mock_event = {'data': 'local_test'}
    mock_context = 'local_context'
    
    # 함수 직접 호출
    result = run_stock_analysis(mock_event, mock_context)
    
    print(f"✅ 로컬 테스트 종료. 최종 결과: {result}")