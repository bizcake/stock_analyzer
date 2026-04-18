# 1. 파이썬 베이스 이미지 지정
FROM python:3.12-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 3. 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 4. 의존성 설치
COPY requirements_web.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 5. 소스 코드 복사
COPY . /app/

# Gunicorn 경로 추가
ENV PATH="/usr/local/bin:$PATH"

# 정적 파일 수집 (이 과정은 DB 접속이 필요 없도록 settings.py가 잘 설정되어 있어야 함)
RUN python manage.py collectstatic --noinput

# 6. 실행 명령 (Cloud Run이 주입해주는 $PORT 환경변수 사용)
CMD exec python -m gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 stocks.wsgi:application