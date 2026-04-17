#!/bin/bash

# 프로젝트 정보 가져오기
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "⚙️  CI/CD 설정을 시작합니다... (Project: $PROJECT_ID)"

# 1. API 활성화
echo "🚀 필요한 API를 활성화합니다..."
gcloud services enable cloudbuild.googleapis.com \
                       run.googleapis.com \
                       cloudfunctions.googleapis.com \
                       artifactregistry.googleapis.com

# 2. Cloud Build 서비스 계정에 권한 부여
echo "🔐 Cloud Build 서비스 계정에 권한을 부여합니다..."

# Cloud Run 배포 권한
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/run.admin"

# Cloud Functions 배포 권한
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/cloudfunctions.admin"

# 서비스 계정 사용 권한 (배포 시 필요)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/iam.serviceAccountUser"

# 소스 업로드 및 이미지 저장 권한
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/storage.admin"

echo "✅ 권한 설정이 완료되었습니다."
echo "💡 이제 GitHub 리포지토리를 생성하고 Cloud Build 트리거를 설정하세요."
