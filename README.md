
python manage.py runserver

python manage.py makemigrations
python manage.py migrate 

python manage.py changepassword mydata
python manage.py createsuperuser hans

python manage.py shell

from analyzer.sync_stock import sync_intraday_today
sync_intraday_today(95)
<!-- analyzer.sync_intraday_today() -->

--구글 로그인
gcloud auth login
--초기화
--config 설정
gcloud config set project stocks-490412
--리젼선택
gcloud config set run/region us-west1

--권한부족
gcloud projects add-iam-policy-binding stocks-490412     --member="serviceAccount:892926059541-compute@developer.gserviceaccount.com"     --role="roles/storage.objectViewer"

--에러로그 확인
gcloud builds list --limit=1

gcloud builds log [빌드-ID]

gcloud beta run services logs tail stocks --project stocks-490412
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=stocks" --project stocks-490412 --limit 10

-- 앱(Cloud Run) 배포
./deploy_app.sh

1) Pub/Sub 주제(Topic) 생성
gcloud pubsub topics create trigger-stock-analysis2

2) Cloud Functions 배포
./deploy_function.sh
    
3. 스케줄러(Cron) 등록
gcloud scheduler jobs create pubsub hourly-stock-analysis \
    --schedule "0 * * * *" \
    --topic trigger-stock-analysis \
    --message-body "run" \
    --time-zone "Asia/Seoul" \
    --location asia-northeast3

gcloud scheduler jobs update pubsub hourly-stock-analysis \
    --schedule "*/30 * * * *" \
    --location asia-northeast3
    
gcloud scheduler jobs list --location=asia-northeast3

gcloud scheduler jobs run hourly-stock-analysis --location=asia-northeast3


echo "# stock_analyzer" >> README.md
git init
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/bizcake/stock_analyzer.git
git push -u origin main
---

## 🚀 CI/CD 및 배포 자동화 (Google Cloud Build)

현재 이 프로젝트는 GitHub 리포지토리에 코드가 푸시되면 자동으로 Google Cloud Build를 통해 **Cloud Run**과 **Cloud Functions**에 배포되도록 설정되어 있습니다.

### 1. 설정 방법

1.  **GitHub 리포지토리 연결**:
    - [GCP Console - Cloud Build 트리거](https://console.cloud.google.com/cloud-build/triggers) 페이지로 이동합니다.
    - **리포지토리 연결**: GitHub(Cloud Build GitHub 앱)를 선택하고 https://github.com/bizcake/stock_analyzer.git 리포지토리를 연결합니다.
    - **트리거 생성**:
        - 이름: `deploy-on-push`
        - 이벤트: `분기로 푸시`
        - 소스: 연결한 리포지토리 및 `main` 분기
        - 구성: `Cloud Build 구성 파일 (yaml)`
        - Cloud Build 구성 파일 위치: `cloudbuild.yaml`
    - **만들기**를 클릭합니다.

2.  **GCP 권한 설정 (이미 완료됨)**:
    - `./setup_cicd.sh` 실행을 통해 Cloud Build 서비스 계정에 필요한 권한(`Cloud Run Admin`, `Cloud Functions Admin` 등)이 부여되었습니다.

### 2. 배포 흐름

1.  로컬에서 코드를 수정하고 GitHub로 `push` 합니다.
2.  Google Cloud Build가 자동으로 감지하여 `cloudbuild.yaml`에 정의된 단계를 실행합니다.
    - Step 1: Docker 이미지 빌드
    - Step 2: Container Registry에 이미지 푸시
    - Step 3: Cloud Run (Django 앱) 배포
    - Step 4: Cloud Functions 배포
3.  배포 상태는 GCP Console의 [Cloud Build 기록](https://console.cloud.google.com/cloud-build/builds)에서 확인할 수 있습니다.

### 3. 환경 변수 관리

- Cloud Build는 기존에 설정된 Cloud Run/Functions의 환경 변수를 유지합니다. 
- 새로운 환경 변수가 필요한 경우 [Secret Manager](https://console.cloud.google.com/security/secret-manager)를 사용하는 것을 권장합니다.
