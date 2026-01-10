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

| 필드명 | 타입 | 필수 | 설명 | 유효성 검사 |
|:--|:--|:--|:--|:--|
| accountId | String | Y | 사용자 계정 ID | 영문/숫자 조합, 4~20자 |
| password | String | Y | 사용자 비밀번호 | 최소 8자, 영문/숫자/특수문자 포함 |
| name | String | Y | 사용자 이름 | 2~20자 |

**비고:** 본인 인증(CI/DI) 데이터는 별도 프로세스에서 검증 후 서버에서 암호화하여 저장합니다.

---

### SignupResponse

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| userId | String | Y | 생성된 사용자 UUID (외부 노출용 식별자) |

---

## 2. 로그인(Login) DTO

### LoginRequest

| 필드명 | 타입 | 필수 | 설명 | 유효성 검사 |
|:--|:--|:--|:--|:--|
| accountId | String | Y | 사용자 계정 ID | 영문/숫자 조합, 4~20자 |
| password | String | Y | 사용자 비밀번호 | 최소 8자 |

---

### LoginResponse

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| accessToken | String | Y | Access Token (JWT) |
| tokenType | String | Y | 토큰 타입 (예: "Bearer") |
| expiresIn | Integer | Y | Access Token 만료 시간 (초 단위) |

**비고:**
- Refresh Token은 응답 Body에 포함하지 않습니다.
- Refresh Token은 **HttpOnly Cookie**로 전달되어 XSS 공격을 방어합니다.
- Cookie 설정: `Path=/api/auth/refresh`, `Secure`, `HttpOnly`, `SameSite=Strict`

---

## 3. 토큰 재발급(Reissue) DTO

### TokenReissueRequest

**Body:** 없음 (Empty Body)

**비고:**
- Refresh Token은 HttpOnly Cookie에서 자동으로 추출됩니다.
- 클라이언트는 요청 Body 없이 `/api/auth/refresh` 엔드포인트를 호출합니다.

---

### TokenReissueResponse

| 필드명 | 타입 | 필수 | 설명 |
|:--|:--|:--|:--|
| accessToken | String | Y | 재발급된 Access Token |
| tokenType | String | Y | 토큰 타입 (예: "Bearer") |
| expiresIn | Integer | Y | Access Token 만료 시간 (초 단위) |

**비고:**
- **RTR(Refresh Token Rotation)** 정책에 따라, 새로운 Refresh Token이 HttpOnly Cookie로 함께 발급됩니다.
- 기존 Refresh Token은 서버에서 자동으로 폐기됩니다.