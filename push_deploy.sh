#!/bin/bash

# 커밋 메시지가 없으면 기본 메시지 사용
COMMIT_MSG=${1:-"Update and deploy"}

echo "🔍 변경사항 확인 중..."
git status

echo "➕ 모든 변경사항 추가 중..."
git add .

echo "💾 커밋 중: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

echo "🚀 GitHub로 푸시 중 (이 작업이 GCP 배포를 트리거합니다)..."
git push origin main

echo "✅ 푸시 완료!"
echo "💡 GCP Console의 Cloud Build 기록에서 배포 진행 상황을 확인하세요:"
echo "👉 https://console.cloud.google.com/cloud-build/builds"
