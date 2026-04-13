#!/bin/bash

# 1. 로컬의 .env 파일을 읽어서 환경변수로 내보냄 (Git에는 올라가지 않는 파일)
if [ -f .env ]; then
  set -a
  source .env
  set +a
else
  echo "❌ .env 파일을 찾을 수 없습니다. 배포를 중단합니다."
  exit 1
fi

# 2. 환경변수를 주입하여 Cloud Functions 배포 실행
echo "🚀 Cloud Functions 배포를 시작합니다..."
gcloud functions deploy stock-analyzer-function \
    --runtime python312 \
    --trigger-topic trigger-stock-analysis \
    --entry-point run_stock_analysis \
    --region asia-northeast3 \
    --memory 1024MB \
    --timeout 540s \
    --set-env-vars DB_HOST="${DB_HOST}",DB_USER="${DB_USER}",DB_PASSWORD="${DB_PASSWORD}",GEMINI_API_KEY="${GEMINI_API_KEY}",TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}",TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"

echo "✅ 펑션 배포가 완료되었습니다!"