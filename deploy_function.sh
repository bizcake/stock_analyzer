#!/bin/bash

# 1. 환경변수 로드 (.env)
if [ -f .env ]; then
  set -a
  source .env
  set +a
else
  echo "❌ .env 파일을 찾을 수 없습니다. 배포를 중단합니다."
  exit 1
fi

# 2. 배포용 임시 폴더(build) 생성 및 초기화
DEPLOY_DIR="deploy_tmp"
rm -rf $DEPLOY_DIR
mkdir -p $DEPLOY_DIR/analyzer
mkdir -p $DEPLOY_DIR/stocks
mkdir -p $DEPLOY_DIR/stock

echo "📦 펑션 배포를 위한 최소 파일 구성 중..."

# 3. 필수 파일만 복사 (화면/웹 관련 소스 및 정적파일 완전 제외)
cp main.py $DEPLOY_DIR/
cp requirements_cf.txt $DEPLOY_DIR/requirements.txt # 전용 requirements로 교체

# 핵심 분석 로직
cp -r analyzer/* $DEPLOY_DIR/analyzer/

# Django 설정 (DB 연결용)
cp -r stocks/* $DEPLOY_DIR/stocks/

# DB 모델 (ORM용)
cp -r stock/* $DEPLOY_DIR/stock/

# 4. 배포 실행 (임시 폴더 내부에서)
echo "🚀 Cloud Functions 배포를 시작합니다..."
cd $DEPLOY_DIR

gcloud functions deploy stock-analyzer-function \
    --runtime python312 \
    --trigger-topic trigger-stock-analysis \
    --entry-point run_stock_analysis \
    --region asia-northeast3 \
    --memory 1024MB \
    --timeout 540s \
    --set-env-vars DB_HOST="${DB_HOST}",DB_USER="${DB_USER}",DB_PASSWORD="${DB_PASSWORD}",GEMINI_API_KEY="${GEMINI_API_KEY}",TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}",TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}",DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY}"

# 5. 후속 정리
cd ..
# rm -rf $DEPLOY_DIR # 배포 확인 후 필요에 따라 삭제

echo "✅ 펑션 배포가 완료되었습니다!"