#!/bin/bash
# [init_airflow.sh]
# 목적: Airflow 환경의 최초 1회 초기화 자동화
# 주요 기능: DB Migration, Admin User 생성

set -e

echo "Starting Airflow Initialization..."

# 1. DB 초기화 및 마이그레이션
# Rationale: 'airflow db migrate'는 기존 데이터 유지하며 스키마만 업데이트하므로 안전함
airflow db migrate

# 2. 관리자 계정 생성
# Rationale: 이미 계정이 존재할 경우 에러가 발생할 수 있으므로, 에러를 무시하거나 존재 여부 체크 권장
airflow users create \
    --username "${_AIRFLOW_WWW_USER_USERNAME:-admin}" \
    --firstname "Admin" \
    --lastname "User" \
    --role Admin \
    --email "${_AIRFLOW_WWW_USER_EMAIL:-admin@example.com}" \
    --password "${_AIRFLOW_WWW_USER_PASSWORD:-admin}" || true

echo "Airflow Initialization Completed Successfully."