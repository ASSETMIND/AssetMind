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
- 회원가입
- 로컬 로그인
- Access Token / Refresh Token 발급
- Refresh Token 기반 Access Token 재발급
- 로그아웃 시 Refresh Token 무효화

### 제외 범위
- 소셜 로그인
- OAuth2 Authorization Code Flow
- 외부 인증 서버 연동


## 3. 도메인 핵심 정책

---
- 인증 수단은 Email + Password만 허용한다.
- Password는 단방향 암호화된 값만 저장한다.
- Access Token은 상태를 가지지 않는다(stateless).
- Refresh Token은 서버에 저장하며, 사용자 기준으로 관리한다.
- 한 사용자는 동시에 하나의 유효한 Refresh Token만 가진다.


## 4. 도메인 엔티티 정의

---

### 4.1 User

**역할**
- 시스템 내 사용자 식별 주체
- 인증 및 권한의 루트 엔티티

**주요 속성**
- id
- email (unique)
- password
- status (ACTIVE / INACTIVE)
- createdAt

**도메인 규칙**
- email은 전역 유니크하다.
- password는 평문으로 존재하지 않는다.


### 4.2 Role
---

**역할**
- 사용자 권한 표현

**주요 속성**
- id
- name (USER, ADMIN 등)

**관계**
- User : Role = N : M


### 4.3 RefreshToken

**역할**
- Access Token 재발급을 위한 인증 수단
- 서버 측에서 생명주기를 관리하는 토큰

**주요 속성**
- id
- userId
- tokenValue
- expiredAt

**도메인 규칙**
- 사용자 1명당 1개의 Refresh Token만 활성 상태로 유지한다.
- 재로그인 시 기존 Refresh Token은 폐기된다.


## 5. 엔티티 관계 요약

---
User 1 — N RefreshToken
User N — M Role


## 6. 책임 분리 기준

---
### Domain
- User / Role / RefreshToken 상태와 제약 조건
- 인증 관련 비즈니스 규칙

### Application(Service)
- 회원가입 및 로그인 흐름 제어
- 토큰 발급 시점 결정

### Security
- JWT 생성
- Access Token 검증
- SecurityContext 인증 정보 주입
