# signals/fixtures/signal_code2.json 또는
# management/commands/init_signal_codes.py 로 초기 데이터 삽입

SIGNAL_CODE2_DATA = [
    # 매수
    {"code": "a00", "name": "적극 매수",      "description": "응축 돌파. 거래량 급증 + 수급 확인. 즉시 진입 검토"},
    {"code": "a01", "name": "강력 매수",      "description": "상승추세 중 과매도 눌림목 반등. 핵심 매수 타점"},
    {"code": "a02", "name": "매수",           "description": "상승추세 + WT 골든크로스. 안전 진입 구간"},
    {"code": "a03", "name": "매수 검토",      "description": "일부 조건 충족. 추가 확인 후 진입"},
    {"code": "a04", "name": "바닥 포착",      "description": "하락추세 중 극단 과매도 반등. 단기 매매만"},
    # 중립
    {"code": "c01", "name": "눌림목 관찰",    "description": "상승추세 중 단기 눌림. 추세 관찰 필요"},
    {"code": "c02", "name": "방향 탐색",      "description": "추세 불명확. 대기"},
    {"code": "c03", "name": "기술적 반등",    "description": "저항 구간 반등. 추세 역행 주의"},
    {"code": "c04", "name": "하락 지속",      "description": "하락추세 유지 중. 진입 금지"},
    # 매도
    {"code": "b01", "name": "매도",           "description": "하락추세 + WT 데드크로스. 보유 청산 고려"},
    {"code": "b02", "name": "매도 주의",      "description": "반등 끝자락. 매도 준비"},
    {"code": "b03", "name": "고점 주의",      "description": "과매수 구간. 신규 진입 금지. 보유자 익절 고려"},
    # 기본
    {"code": "d01", "name": "관망",           "description": "분석 대기 또는 신호 없음"},
]

# management/commands/init_signal_codes.py
from django.core.management.base import BaseCommand
from stock.models import SignalCode2

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for data in SIGNAL_CODE2_DATA:
            SignalCode2.objects.update_or_create(
                code=data['code'],
                defaults={'name': data['name'], 'description': data['description']}
            )
        self.stdout.write("✅ SignalCode2 초기 데이터 완료")