# API 명세서 작성 가이드 (API Documentation Guide)

| 문서 ID       | GUIDE-API-001          |
| :------------ | :--------------------- |
| **문서 버전** | 1.0                    |
| **프로젝트** | AssetMind              |
| **작성자** | 김준수                 |
| **작성일** | 2025년 12월 14일       |

---

## 1. 개요
본 문서는 AssetMind 시스템의 프론트엔드(Client)와 백엔드(Server) 간 데이터 통신을 위한 인터페이스(API) 정의 표준을 기술한다. 모든 API 명세는 본 가이드에 따라 작성되어야 하며, 이는 개발 단계에서의 혼선을 줄이고 연동 테스트의 효율을 높이는 것을 목적으로 한다.

---

## 2. 기본 원칙 (General Principles)

### 2.1. 프로토콜 및 포맷
* **Protocol**: HTTP/1.1 (HTTPS 권장)
* **Data Format**: JSON (Content-Type: `application/json`)
* **Character Set**: UTF-8

### 2.2. Base URL 구조
모든 API의 엔드포인트는 아래의 기본 경로를 따른다.
`https://[domain]/api/[version]/[resource]`
* 예: `https://api.assetmind.com/api/v1/stocks`

### 2.3. 명명 규칙 (Naming Conventions)
* **URI (Resource)**: 소문자와 하이픈(`-`)을 사용하는 **Kebab-case**를 권장하며, 리소스는 **복수형 명사**를 사용한다.
    * (O) `/api/v1/users`, `/api/v1/portfolio-items`
    * (X) `/api/v1/getUser`, `/api/v1/portfolio_items`
* **JSON Key**: 데이터 응답 본문의 키 값은 Python 백엔드 환경을 고려하여 **Snake_case**를 기본으로 한다.
    * (O) `{"user_id": 1, "created_at": "2025-12-14"}`

---

## 3. HTTP 메서드 정의
리소스에 대한 행위는 HTTP Method로 명확히 구분한다.

| 메서드 | 역할 | 설명 |
| :--- | :--- | :--- |
| **GET** | 조회 | 리소스의 상태를 조회한다. (Body 사용 금지, Query String 사용) |
| **POST** | 생성 | 새로운 리소스를 생성한다. |
| **PUT** | 수정 | 리소스 전체를 수정(교체)한다. |
| **PATCH** | 수정 | 리소스의 일부 필드만 부분 수정한다. |
| **DELETE**| 삭제 | 리소스를 삭제한다. |

---

## 4. API 명세 구성 요소
각 API 정의는 다음 항목을 반드시 포함해야 한다.

| 항목 | 설명 |
| :--- | :--- |
| **API ID** | `API-[주제약어]-[번호]` (예: `API-KIS-001`) |
| **API 명** | API 기능을 요약한 제목 |
| **Endpoint** | Method와 URI (예: `GET /stocks/{symbol}`) |
| **Description** | API의 상세 기능 및 주의사항 설명 |
| **Request** | Header, Path Param, Query Param, Request Body 정의 |
| **Response** | HTTP Status Code별 응답 예시 및 스키마 정의 |

---

## 5. 응답 코드 (HTTP Status Codes)
클라이언트가 처리 로직을 분기할 수 있도록 표준 상태 코드를 준수한다.

| 코드 | 상태 | 설명 |
| :--- | :--- | :--- |
| **200** | OK | 요청이 성공적으로 처리됨 (주로 조회, 수정) |
| **201** | Created | 요청이 성공하여 새로운 리소스가 생성됨 (POST) |
| **204** | No Content | 요청은 성공했으나 응답할 본문 데이터가 없음 (DELETE 등) |
| **400** | Bad Request | 필수 파라미터 누락, 유효성 검증 실패 등 클라이언트 오류 |
| **401** | Unauthorized | 인증 토큰이 없거나 유효하지 않음 (로그인 필요) |
| **403** | Forbidden | 리소스에 대한 접근 권한이 없음 (본인 데이터가 아님) |
| **404** | Not Found | 요청한 URI 또는 리소스가 존재하지 않음 |
| **500** | Server Error | 서버 내부 로직 에러 (DB 연결 실패, Null Pointer 등) |

---

## 6. 작성 예시

### 예시: 사용자 회원가입 (API-AUTH)

| 항목 | 내용 |
| :--- | :--- |
| **API ID** | `API-AUTH-001` |
| **API 명** | 신규 회원가입 (User Registration) |
| **Endpoint** | **POST** `/api/v1/auth/signup` |
| **설명** | 사용자의 이메일, 비밀번호, 이름을 입력받아 새로운 계정을 생성한다.<br>비밀번호는 서버 측에서 반드시 암호화(Hashing)되어 저장된다. |
| **Request** | **[Headers]**<br>- `Content-Type`: application/json<br><br>**[Body]**<br>`{`<br>&nbsp;&nbsp;`"email": "junsu.kim@example.com",`<br>&nbsp;&nbsp;`"password": "Password123!",`<br>&nbsp;&nbsp;`"name": "김준수",`<br>&nbsp;&nbsp;`"marketing_agree": true`<br>`}` |
| **Response**<br>**(Success)** | **Code**: `201 Created`<br>**Body**:<br>`{`<br>&nbsp;&nbsp;`"success": true,`<br>&nbsp;&nbsp;`"user_id": 105,`<br>&nbsp;&nbsp;`"message": "회원가입이 완료되었습니다."`<br>`}` |
| **Response**<br>**(Error)** | **Code**: `400 Bad Request` (입력값 오류)<br>`{`<br>&nbsp;&nbsp;`"error_code": "INVALID_EMAIL_FORMAT",`<br>&nbsp;&nbsp;`"message": "이메일 형식이 올바르지 않습니다."`<br>`}`<br><br>**Code**: `409 Conflict` (중복 가입)<br>`{`<br>&nbsp;&nbsp;`"error_code": "EMAIL_ALREADY_EXISTS",`<br>&nbsp;&nbsp;`"message": "이미 가입된 이메일입니다."`<br>`}` |
