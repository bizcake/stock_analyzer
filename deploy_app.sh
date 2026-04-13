#!/bin/bash

# 1. 로컬의 .env 파일을 읽어서 환경변수로 내보냄
if [ -f .env ]; then
  set -a
  source .env
  set +a
else
  echo "❌ .env 파일을 찾을 수 없습니다. 배포를 중단합니다."
  exit 1
fi

# 2. 환경변수를 주입하여 Cloud Run(장고 앱) 배포 실행
echo "🚀 Cloud Run(웹 앱) 배포를 시작합니다..."
gcloud run deploy stocks \
    --source . \
    --region us-west1 \
    --memory 1Gi \
    --allow-unauthenticated \
    --update-env-vars DB_HOST="${DB_HOST}",DB_USER="${DB_USER}",DB_PASSWORD="${DB_PASSWORD}",DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY}"

echo "✅ 앱 배포가 완료되었습니다!"