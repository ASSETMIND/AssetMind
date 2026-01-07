# API-AUTH-LOCAL-DTO-001
회원가입 / 로그인 Request · Response DTO 명세

| 문서 ID | API-AUTH-LOCAL-DTO-001 |
|:------|:------------------------|
| 문서 버전 | 1.0 |
| 프로젝트 | AssetMind |
| 작성자 | 김광래 |
| 작성일 | 2026년 1월 7일 |

---

## 1. 회원가입(Signup) DTO

### SignupRequest

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| email | String | Y | 사용자 이메일 |
| password | String | Y | 사용자 비밀번호 |

---

### SignupResponse

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| userId | Long | Y | 생성된 사용자 ID |

---

## 2. 로그인(Login) DTO

### LoginRequest

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| email | String | Y | 사용자 이메일 |
| password | String | Y | 사용자 비밀번호 |

---

### LoginResponse

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| accessToken | String | Y | Access Token |
| refreshToken | String | Y | Refresh Token |

---

## 3. 토큰 재발급(Reissue) DTO

### TokenReissueRequest

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| refreshToken | String | Y | 기존 Refresh Token |

---

### TokenReissueResponse

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| accessToken | String | Y | 재발급된 Access Token |