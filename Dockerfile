# Dockerfile
# Python 3.12 slim 기반 — Streamlit + LangChain + psycopg2 포함

FROM python:3.12-slim

# 시스템 의존성 (psycopg2-binary 빌드용 libpq 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements 먼저 복사 → 레이어 캐시 활용
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY .env.example .env.example

# SQLite DB 저장 디렉터리
RUN mkdir -p /app/data

# Streamlit 기본 설정 (헤드리스 모드)
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    PYTHONPATH=/app/backend

EXPOSE 8501

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "frontend/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0"]