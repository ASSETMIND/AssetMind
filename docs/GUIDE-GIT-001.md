# Git 브랜치 전략 및 협업 가이드

| 문서 ID       | GUIDE-GIT-001 |
| :------------ | :--------------------- |
| **문서 버전** | 1.0                    |
| **프로젝트**  | AssetMind               |
| **작성자**    | 김준수                 |
| **작성일**    | 2025년 12월 14일         |

## 1. 개요 (Overview)
본 문서는 팀 프로젝트의 개발 생산성과 협업 효율성을 극대화하기 위한 **Git 브랜치 전략** 및 **커밋 컨벤션**을 정의합니다. 
우리는 **Git-flow**를 기반으로 하며, 명확한 **이슈 추적(Issue Tracking)**과 **작업자 식별**, **코드의 기술적 계층 분류**를 최우선으로 합니다.

---

## 2. 브랜치 전략 (Branch Strategy)

### 2.1 브랜치 구조
프로젝트는 다음 5가지 브랜치 타입을 중심으로 운영됩니다.

| 브랜치 타입 | 명명 규칙 (Prefix) | 설명 및 역할 | 관리 주체 |
| :--- | :--- | :--- | :--- |
| **Main** | `main` | **배포 가능한 상태(Production Ready)**의 최종 코드 저장소. 직접 Push 금지. | 팀장 |
| **Develop** | `develop` | **개발 중인 코드**가 모이는 중심 브랜치. 모든 Feature는 여기서 파생/병합됨. | 팀 전원 |
| **Feature** | `feature/...` | **단위 기능 개발** 브랜치. 작업 완료 후 `develop`으로 PR. | 개별 개발자 |
| **Release** | `release/...` | 배포 전 QA 및 최종 점검을 위한 브랜치. | 팀장 |
| **Hotfix** | `hotfix/...` | `main` 배포 후 발생한 **긴급 버그 수정** 브랜치. | 담당자 |

### 2.2 Feature 브랜치 명명 규칙
이슈 트래킹 연동과 동시 작업 충돌 방지를 위해 아래 형식을 엄격히 준수합니다.

> **포맷:** `feature/#[이슈번호]-[기능명]-[이니셜]`

* **[이슈번호]**: Github Issue / Jira 티켓 번호 (`#` 포함)
* **[기능명]**: 기능을 명확히 설명하는 단어 (PascalCase 권장)
* **[이니셜]**: 개발자 본인의 영문 이니셜 (대문자 2~3글자)

예시 : **`feature/#1-LoginApi-KJS`**

### 2.3 기타 브랜치 명명 규칙
* **Release:** `release/v[버전]` (예: `release/v1.0.0`)
* **Hotfix:** `hotfix/v[버전]-fix` (예: `hotfix/v1.0.1-security-patch`)

---

## 3. 커밋 메시지 컨벤션 (Commit Convention)

모든 커밋은 **이슈 번호**, **작업 유형(Type)**, **기술 영역(Scope)**을 명시해야 합니다.

> **포맷:** `#이슈번호 - [TYPE] SCOPE : 한글 메시지`

### 3.1 TYPE (작업 유형)
대문자로 작성합니다.

| TYPE | 설명 |
| :--- | :--- |
| **FEAT** | 새로운 기능 추가 |
| **FIX** | 버그 수정 |
| **DOCS** | 문서 수정 (README, Wiki 등) |
| **STYLE** | 코드 포맷팅 (로직 변경 없음, 세미콜론 등) |
| **REFACTOR** | 코드 리팩토링 (기능 변경 없음, 구조 개선) |
| **TEST** | 테스트 코드 추가/수정 |
| **CHORE** | 빌드, 패키지 설정, 라이브러리 설치 등 |
| **DESIGN** | UI/CSS 디자인 수정 (FE 전용) |

### 3.2 SCOPE (기술 계층)
작업이 수행된 기술적 위치(Layer)를 명시합니다. 대문자로 작성합니다.

#### A. Backend (Spring Boot)
| SCOPE | 설명 |
| :--- | :--- |
| **API** | API 엔드포인트, Controller |
| **SERVICE** | 비즈니스 로직, 트랜잭션 |
| **DB** | Repository, Entity, SQL, JPA |
| **DTO** | Request/Response 객체 |
| **SECURITY** | 인증/인가, JWT, Security Config |
| **UTIL** | 공통 유틸리티 |
| **TEST** | 단위/통합 테스트 코드 |
| **ERROR** | ExceptionHandler, 에러 코드 |

#### B. Frontend (React)
| SCOPE | 설명 |
| :--- | :--- |
| **VIEW** | UI 컴포넌트, 페이지 |
| **API** | 서버 통신 로직 (Axios, React Query) |
| **DTO** | Type/Interface 정의 |
| **DB** | LocalStorage, Cookie 등 클라이언트 저장소 |
| **STATE** | 전역 상태 관리 (Recoil, Redux) |
| **HOOK** | 커스텀 훅 |
| **STYLE** | CSS, Global Style |
| **ASSET** | 이미지, 폰트, 아이콘 |

#### C. Data Engineering (Airflow/Python)
| SCOPE | 설명 |
| :--- | :--- |
| **ETL** | 추출/변환/적재 파이프라인 |
| **DB** | DWH/마트 스키마(DDL), 쿼리 |
| **CRAWL** | 크롤링/스크래핑 스크립트 |
| **MODEL** | 데이터 모델, 분석 알고리즘 |
| **CONN** | DB 커넥션, 외부 연동 설정 |
| **DAG** | Airflow DAG 정의 |
| **PREPROC** | 전처리 및 정제 로직 |

#### D. Common (공통)
| SCOPE | 설명 |
| :--- | :--- |
| **CONFIG** | 환경 설정 (yml, env) |
| **DEP** | 의존성 관리 (gradle, package.json) |
| **CI** | CI/CD 스크립트 |
| **INFRA** | 클라우드 리소스 (AWS, Docker) |

#### ✅ 커밋 메시지 예시
> `#10 - [FEAT] API : 로그인 검증 로직 구현`
> `#10 - [FIX] DB : User 엔티티 컬럼 속성 수정`
> `#10 - [DESIGN] VIEW : 로그인 버튼 호버 효과 추가`

---

## 4. 작업 워크플로우 (Workflow)

### Step 1. 브랜치 생성
`develop`을 최신화한 후 규칙에 맞춰 생성합니다. (터미널에서 `#` 입력 시 따옴표 필수)
```bash
git checkout develop
git pull origin develop
git checkout -b "feature/#1-LoginApi-KJS"
