FROM apache/airflow:2.10.2-python3.12

USER root

# OS 패키지 설치 및 캐시 클린업 체인
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

ENV POETRY_VERSION=2.0.0
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# [CRITICAL FIXED]: Lock 파일을 함께 복사하여 패키지 버전 고정
COPY pyproject.toml poetry.lock ./ 

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root