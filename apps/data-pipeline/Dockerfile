# [Dockerfile]
FROM apache/airflow:2.10.2-python3.12

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

ENV POETRY_VERSION=2.0.0
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml ./ 

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root