
python manage.py runserver

python manage.py makemigrations
python manage.py migrate 

python manage.py changepassword mydata
python manage.py createsuperuser hans

python manage.py shell


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
gcloud pubsub topics create trigger-stock-analysis

2) Cloud Functions 배포
./deploy_function.sh
    
3. 스케줄러(Cron) 등록
gcloud scheduler jobs create pubsub hourly-stock-analysis \
    --schedule "0 * * * *" \
    --topic trigger-stock-analysis \
    --message-body "run" \
    --time-zone "Asia/Seoul" \
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