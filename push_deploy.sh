#!/bin/bash

# 커밋 메시지 설정
COMMIT_MSG=${1:-"Update and deploy"}

echo "🔍 변경사항 확인 중..."
git status

# 변경사항이 있는지 확인
if [ -z "$(git status --porcelain)" ]; then
    echo "✨ 변경사항이 없습니다. 커밋을 건너뜁니다."
else
    echo "➕ 모든 변경사항 추가 중..."
    git add .

    echo "💾 커밋 중: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
fi

echo "🚀 GitHub로 푸시 중 (origin main)..."
if git push origin main; then
    echo "✅ 푸시 성공! GitHub에 코드가 반영되었습니다."
    echo "💡 GCP Cloud Build 트리거가 설정되어 있다면 자동으로 배포가 시작됩니다."
else
    echo "❌ 푸시 실패!"
    echo "💡 권한 문제(403)가 발생한다면 다음 명령어로 GitHub 토큰을 설정하세요:"
    echo "   git remote set-url origin https://<유저네임>:<토큰>@github.com/bizcake/stock_analyzer.git"
    exit 1
fi

echo "🔗 배포 상태 확인(GCP): https://console.cloud.google.com/cloud-build/builds?project=stocks-490412"
