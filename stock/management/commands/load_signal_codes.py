from django.core.management.base import BaseCommand
from stock.models import SignalCode

class Command(BaseCommand):
    help = "시그널 공통코드 데이터를 데이터베이스에 적재합니다."

    def handle(self, *args, **options):
        signals = [
            # {"code": "a01", "name": "🔥 강력 매수 (완벽한 눌림목 타점)", "description": "최우선 순위. 정배열+수급+스토캐스틱 최적 타점"},
            # {"code": "a02", "name": "✅ 매수 (바닥탈출 시도)", "description": "역배열에서 수급이 들어오며 머리를 드는 시점"},
            # {"code": "a03", "name": "✅ 매수 (상승 추세 지속)", "description": "기존 상승 흐름이 안정적으로 유지됨"},
            # {"code": "a04", "name": "📉 찐바닥 포착 (매수 대기)", "description": "과매도 구간에서 반등 신호 포착"},
            # {"code": "b01", "name": "📉 매도 (추세이탈)", "description": "위험. 장기 이평선 및 지지선 이탈"},
            # {"code": "b02", "name": "⚠️ 매도 주의 (반등 끝자락)", "description": "단기 반등 후 다시 꺾이는 지점"},
            # {"code": "b03", "name": "⚠️ 관망 (단기 고점 의심)", "description": "과매수 구간 진입으로 인한 조정 대비"},
            # {"code": "c01", "name": "↔️ 기술적 반등 (저항주의)", "description": "하락 추세 중 일시적 반등"},
            # {"code": "c02", "name": "↔️ 방향 탐색 중", "description": "에너지가 응축되며 변동성이 줄어든 구간"},
            {"code": "c03", "name": "⚠️ 변동성 확대 (급격한 추세 전환)", "description": "에너지가 폭발하며 상하방 변동성이 극심해진 구간"},
            {"code": "c04", "name": "⚠️ 과매수/과열권 (차익실현 권장)", "description": "지표상 단기 과열권에 진입하여 조정 가능성이 높은 구간"},
            # {"code": "d01", "name": "Hold (관망)", "description": "무포지션 유지 구간"},
        ]

        count = 0
        for sig in signals:
            # update_or_create를 사용하여 중복 생성 방지 및 내용 갱신
            obj, created = SignalCode.objects.update_or_create(
                code=sig["code"],
                defaults={
                    "name": sig["name"],
                    "description": sig["description"]
                }
            )
            if created:
                count += 1

        self.stdout.write(f"✅ 총 {len(signals)}개의 시그널 코드가 확인되었으며, {count}개가 새로 등록되었습니다.")