# ARC-AUTH-LOCAL-001
로컬 로그인(Local Login) 기반 인증 도메인 설계 명세

| 문서 ID | ARC-AUTH-LOCAL-001 |
|:------|:-------------------|
| 문서 버전 | 1.0 |
| 프로젝트 | AssetMind |
| 작성자 | 김광래 |
| 작성일 | 2026년 1월 6일 |

---

## 1. 문서 목적

---
본 문서는 AssetMind 프로젝트에서 사용하는  
로컬 로그인(ID/PW) 기반 인증 도메인의 구조와 핵심 엔티티를 정의한다.

본 문서는 다음을 다룬다.
- 인증 도메인의 책임 범위
- User / Role / RefreshToken 엔티티 구조
- 토큰 발급과 저장에 대한 도메인 관점의 기준

API 스펙, 컨트롤러 흐름, 프론트 연동 내용은 본 문서 범위에 포함하지 않는다.


## 2. 인증 도메인 범위

---
### 포함 범위
- 본인 인증 (포트원 연동)
- 회원가입 (ID 기반)
- 로컬 로그인 (ID + Password)
- Access Token / Refresh Token 발급
- Refresh Token 기반 Access Token 재발급 (RTR 적용)
- 로그아웃 시 Refresh Token 무효화
- 계정 보안 (로그인 실패 카운터, 계정 잠금)

### 제외 범위
- 소셜 로그인
- OAuth2 Authorization Code Flow
- 외부 인증 서버 연동


## 3. 도메인 핵심 정책

---
- 인증 수단은 계정 ID + Password만 허용한다.
- Password는 Argon2 알고리즘으로 해싱하여 저장한다.
- Access Token은 상태를 가지지 않는다(stateless).
- Refresh Token은 MySQL에 해시값으로 저장하며, 사용자 기준으로 관리한다.
- **단일 세션 정책:** 한 사용자는 동시에 하나의 유효한 Refresh Token만 가진다.
  - 재로그인 시 기존 세션이 무효화된다. (PC에서 로그인 후 모바일 로그인 시 PC 세션 종료)
  - 금융 서비스 보안 특성상 멀티 디바이스를 지원하지 않는다.
- 로그인 실패 5회 시 계정이 잠긴다.
- 본인 인증 데이터(CI/DI)는 암호화하여 저장한다.


## 4. 도메인 엔티티 정의

---

### 4.1 User (도메인 모델)

**역할**
- 시스템 내 사용자 식별 주체
- 인증 및 권한의 루트 엔티티

**주요 속성**
- id (내부 PK)
- uuid (외부 노출용 식별자)
- accountId (unique)
- password (Argon2 해시)
- name (사용자 이름)
- role (Enum: USER, ADMIN)
- status (Enum: ACTIVE, INACTIVE, LOCKED)
- loginFailCount (로그인 실패 횟수)
- lastLoginAt (마지막 로그인 시각)
- passwordChangedAt (비밀번호 변경 시각)
- ciValue (암호화된 본인 인증 CI)
- diValue (암호화된 본인 인증 DI)
- createdAt
- updatedAt

**도메인 규칙**
- accountId는 전역 유니크하다.
- password는 평문으로 존재하지 않는다.
- loginFailCount가 5회 이상이면 status가 LOCKED로 변경된다.
- CI/DI 값은 중복 가입 방지에 사용된다.

---

### 4.2 Role (단순화)
---

**역할**
- 사용자 권한 표현

**구현 방식**
- User 엔티티 내 Enum 필드로 관리
- `UserRole` Enum: USER, ADMIN

**변경 이유:**
- 권한이 단순(USER/ADMIN)하여 별도 테이블(N:M) 구성은 오버 엔지니어링
- 조회 성능 향상 (JOIN 불필요)
- 향후 복잡한 권한 체계 필요 시 리팩토링 가능

---

### 4.3 RefreshToken (MySQL Entity)

**역할**
- Access Token 재발급을 위한 인증 수단
- 서버 측에서 생명주기를 관리하는 토큰

**저장 위치**
- MySQL (RDB - JPA Entity)

**주요 속성**
- id (PK)
- userId (FK - User 참조)
- tokenHash (SHA-256 해시값 - **원문은 저장하지 않음**)
- clientIp (요청 IP 주소)
- userAgent (접속 기기/브라우저 정보)
- issuedAt
- expiredAt
- createdAt
- updatedAt

**도메인 규칙**
- 사용자 1명당 1개의 Refresh Token만 활성 상태로 유지한다.
- 재로그인 시 기존 Refresh Token은 폐기된다.
- DB 탈취 시에도 원문 토큰이 없어 세션 하이재킹이 불가능하다.
- IP/User-Agent 변경 시 의심 활동으로 간주할 수 있다.
- 만료된 토큰은 배치 작업으로 주기적으로 삭제한다.


## 5. 엔티티 관계 요약

---
User 1 — 1 RefreshToken (MySQL)
User.role → UserRole Enum

**비고:**
- RefreshToken은 User와 1:1 관계로 매핑됩니다. (단일 세션 정책)
- Role은 별도 테이블이 아닌 User 엔티티의 Enum 필드입니다.
- RefreshToken은 orphanRemoval=true로 설정하여 User 삭제 시 자동 삭제됩니다.

---

## 6. JWT 토큰 구조

### Access Token Payload

| 필드명 | 설명 |
|:--|:--|
| sub | 사용자 UUID (외부 식별자) |
| role | 사용자 권한 (예: "USER") |
| iat | 발급 시각 (Unix Timestamp) |
| exp | 만료 시각 (Unix Timestamp) |

### Refresh Token Payload

| 필드명 | 설명 |
|:--|:--|
| sub | 사용자 UUID |
| type | "refresh" (토큰 타입 구분) |
| iat | 발급 시각 |
| exp | 만료 시각 |

**비고:**
- Access Token에는 인가에 필요한 최소 정보만 포함한다.
- Refresh Token은 재발급 전용이므로 role 정보를 포함하지 않는다.


## 7. 책임 분리 기준

---
### Domain Layer (순수 비즈니스 로직)
- User / RefreshToken 상태와 제약 조건
- 인증 관련 비즈니스 규칙
- 도메인 이벤트 정의

### Application Layer (흐름 제어)
- 회원가입 및 로그인 흐름 제어
- 토큰 발급 시점 결정
- 트랜잭션 경계 관리

### Infrastructure Layer (기술 구현체)
- **Persistence:** JPA Entity를 통한 User / RefreshToken 저장/조회
- **Security:** JWT 생성, 검증, SecurityContext 주입
- **External API:** 본인 인증(포트원) 연동
- **Batch:** 만료된 RefreshToken 주기적 삭제

### Presentation Layer (외부 인터페이스)
- HTTP 요청/응답 처리
- DTO 검증 (Validation)
- 인증 결과 반환
