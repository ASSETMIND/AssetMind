# 데이터 파이프라인 명세서 작성 가이드 (Data Pipeline Spec Guide)

| 문서 ID       | GUIDE-DE-001          |
| :------------ | :--------------------- |
| **문서 버전** | 1.0                    |
| **프로젝트** | AssetMind              |
| **작성자** | 김준수                 |
| **작성일** | 2025년 12월 14일       |

---

## 1. 개요
본 문서는 AssetMind 프로젝트의 데이터 수집, 변환, 적재(ETL/ELT) 과정을 정의하는 '데이터 파이프라인 명세서'의 작성 표준을 정의한다. 본 가이드는 데이터의 **정합성(Consistency), 추적성(Lineage), 운영 안정성(Stability)**뿐만 아니라 **보안(Security) 및 리소스 최적화(Cost Efficiency)**를 보장하는 것을 목적으로 한다.

---

## 2. 명세서 구성 요소
하나의 데이터 파이프라인 명세서(`ETL-[주제약어]-[번호]`)는 개발 및 운영(DevOps) 관점에서 필요한 다음의 상세 항목들을 포함해야 한다.

| 항목 | 설명 | 핵심 키워드 |
| :--- | :--- | :--- |
| **Pipeline ID** | `ETL-[주제약어]-[번호]` | 식별자 |
| **Overview** | 파이프라인의 목적, 비즈니스 가치, 데이터 오너십 | R&R, Governance |
| **Schedule & Configuration** | 실행 주기, 재시도 정책, 리소스 할당량, **Catchup 정책** | Resource, Cost |
| **Data Flow & Security** | Source/Sink 경로 및 **인증 정보(Secrets) 관리 방안** | Security, Lineage |
| **Schema Mapping** | 컬럼 매핑, 타입 변환, **개인정보 비식별화 여부** | Transformation, Privacy |
| **Quality & Operations** | 유효성 검증, **데이터 보존 주기(Retention)**, 장애 대응 | DQ, SLA, Monitoring |

---

## 3. 상세 작성 규칙

### 3.1. 기본 정보 및 구성 (General & Config)
* **Trigger**: Cron 표현식과 함께 **Catchup(과거 데이터 소급 실행) 여부**를 명시한다.
* **Resources**: 작업 수행에 필요한 예상 리소스(Worker Type, Memory)를 명시하여 비용 효율성을 고려한다.

### 3.2. 보안 및 입출력 (Security & I/O)
* **Secrets**: API Key, DB Password 등 민감 정보는 환경변수나 Secret Manager를 참조하도록 명시한다 (하드코딩 금지).
* **Format**: 저장 포맷(Parquet, Avro 등)과 압축 방식(Snappy, Zstd)을 기술한다.

### 3.3. 데이터 품질 및 거버넌스 (Quality & Governance)
* **Schema Evolution**: 원천 데이터 스키마 변경 시 대응 전략(Fail, Merge, Ignore)을 정의한다.
* **Retention**: 데이터의 생명주기(Cold Storage 이관 또는 삭제 주기)를 정의한다.

---

## 4. 작성 예시

### 예시: KRX 일별 시세 수집 및 정제 (ETL-KRX)

| 항목 | 내용 |
| :--- | :--- |
| **Pipeline ID** | `ETL-KRX-001` |
| **파이프라인명** | KRX 전종목 일별 시세 수집 및 Data Lake 적재 |
| **목적** | 한국거래소(KRX) API를 통해 전일자 국내 상장 전종목의 시세 정보를 수집하여 변동성 모델 학습을 위한 기초 데이터(Bronze Layer)를 생성한다. |
| **담당자** | 김준수 (Data Engineer) |

#### 4.1. 스케줄 및 환경 설정 (Schedule & Env)

| 설정 항목 | 값/설명 | 비고 |
| :--- | :--- | :--- |
| **Schedule** | `0 8 * * *` (매일 08:00 KST) | 장 시작(09:00) 전 적재 완료 목표 (SLA: 30분) |
| **Catchup** | `False` | 배포 시점 이전의 과거 데이터는 별도 Backfill DAG로 수행 |
| **Concurrency** | `Max Active Runs: 1` | 중복 실행 방지 및 데이터 정합성 보장 |
| **Resource** | `Worker: t3.medium` (2 vCPU, 4GB RAM) | 일일 처리량 약 3,000건 미만으로 소형 인스턴스 사용 |

#### 4.2. 데이터 흐름 및 보안 (Data Flow & Security)

| 단계 | 시스템/Type | 상세 정보 | 보안 및 인증 (Secrets) |
| :--- | :--- | :--- | :--- |
| **Source** | External API | **KRX 정보데이터 시스템**<br>- Path: `/daily-price` | `AWS Secrets Manager`<br>Key: `prod/krx/api-key` |
| **Process** | Airflow (Python) | **Task Flow**<br>1. `extract`: API 호출 (Rate Limit: 100 req/sec)<br>2. `anonymize`: 민감 정보 마스킹 (해당 없음)<br>3. `convert`: JSON → Parquet 변환 | - |
| **Sink** | AWS S3 (Data Lake) | **Path**: `s3://assetmind-dl-bronze/krx/price/`<br>**Partition**: `/yyyy=2025/mm=12/dd=14/`<br>**Format**: Parquet (Snappy Compressed) | IAM Role 기반 접근 제어<br>(`role-airflow-worker`) |

#### 4.3. 필드 매핑 및 변환 로직 (Schema Mapping)

| Source Field | Target Field | Type | Nullable | 변환 로직 (Transformation Rule) |
| :--- | :--- | :--- | :--- | :--- |
| `ISU_CD` | `symbol_code` | String | **No** | 그대로 매핑 (PK) |
| `ISU_NM` | `item_name` | String | Yes | `trim()` 및 특수문자 제거 정제 |
| `TDD_CLSPRC` | `close_price` | Long | **No** | 콤마 제거 후 Long 변환 (음수일 경우 Error) |
| `TDD_OPNPRC` | `open_price` | Long | Yes | Null/0 인 경우 `prev_close` 값으로 대체 (결측치 보정) |
| *(Derived)* | `collected_at` | Timestamp | **No** | `current_timestamp()` (KST 기준) |
| *(Derived)* | `data_date` | Date | **No** | Airflow `{{ execution_date }}` 기준 (Partition Key) |

#### 4.4. 운영 및 장애 대응 (Operations & Governance)

| 구분 | 상세 정책 |
| :--- | :--- |
| **유효성 검사** | **1. Schema Check**: 필수 컬럼 누락 시 파이프라인 즉시 실패 (`Fail Fast`)<br>**2. Volume Check**: 레코드 수 < 2,000건 시 `Warning` 알림 (휴장일 로직 별도 적용)<br>**3. Integrity**: `symbol_code` 중복 발생 시 `Drop Duplicates` 후 적재 |
| **재시도(Retry)** | **Policy**: `retries=3`, `retry_delay=5 mins`<br>**Strategy**: API Timeout/Conn Error 시에만 재시도 (로직 에러 시 즉시 실패) |
| **멱등성(Idempotency)** | **보장 방식**: `Overwrite` 모드 사용. 동일 `data_date` 파티션에 대해 여러 번 수행하더라도 결과가 항상 같도록 해당 파티션을 삭제 후 재적재(Delete-Insert) 방식 적용 |
| **보존 주기(Retention)** | Raw Data(Bronze)는 **영구 보관**, 처리 로그는 **90일 후 삭제** |
