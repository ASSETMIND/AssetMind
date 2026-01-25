# [TCS] 사용자(User) 메일 전송 어댑터 테스트 명세서

| 문서 ID | **TCS-INFRA-MAIL-001** |
| :--- | :--- |
| **문서 버전** | 1.0 |
| **프로젝트** | AssetMind |
| **작성자** | 이재석 |
| **작성일** | 2026년 01월 19일 |
| **관련 모듈** | `apps/server-auth/user/infrastructure/mail` |

## 1. 개요 (Overview)

본 문서는 AssetMind 인증 서버의 메일 발송 기능을 담당하는 **`EmailSenderAdapter`** (Adapter)의 동작을 검증하기 위한 단위 테스트(Unit Test) 명세이다.
`Mockito`를 사용하여 외부 시스템(Google SMTP/JavaMailSender)을 모킹(Mocking) 처리하고, 메일 발송 요청 시 데이터 전달의 정확성과 예외 발생 시의 안정성을 중점적으로 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito
- **Target Class:** `EmailSenderAdapterTest`
- **Key Verification:**
    - **Metadata Integrity:** 수신자(targetAddress)와 제목(Subject)이 `MimeMessage`에 올바르게 설정되는지 검증
    - **Behavior Verification:** `JavaMailSender`의 `send()` 메서드가 정상적으로 호출되는지 검증
    - **Fault Tolerance:** 메일 전송 중 런타임 예외(SMTP 연결 실패 등) 발생 시, 애플리케이션이 중단되지 않고 로그 처리 후 안전하게 종료되는지 검증

---

## 2. Infrastructure Adapter 테스트 명세
> **대상 클래스:** `EmailSenderAdapterTest`
> **검증 목표:** 도메인 계층의 메일 발송 요청이 인프라 계층(JavaMailSender)으로 올바르게 전달되며, 비동기 실행 환경에서의 예외 처리가 견고한지 보장

### 2.1. 발송 (Send) 검증

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-MAIL-001** | `givenMailMessage_`<br>`whenSendEmail_thenCorrectMailMessage`<br>👉 **정상적인 메일 정보를 받아 발송 요청을 수행한다.** | **전송 데이터 준비**<br>(수신자, 제목, 본문)<br>**Mock 설정**<br>(`createMimeMessage` 호출 시 실제 객체 반환) | **`emailSenderAdapter.sendEmail()`** | 1. `javaMailSender.send()`가 **1회 호출**된다.<br>2. `ArgumentCaptor`로 포획한 메세지 검증:<br>&nbsp;&nbsp;- **수신자**가 입력값과 일치한다.<br>&nbsp;&nbsp;- **제목**이 입력값과 일치한다. |
| **INF-MAIL-002** | `givenMailMessage_`<br>`whenSendEmail_thenDoesNotThrowException`<br>👉 **메일 전송 중 예외 발생 시 전파되지 않고 처리된다.** | **전송 데이터 준비**<br>**Mock 설정 (Unhappy Case)**<br>(`send()` 호출 시 `MailSendException` 발생 설정) | **`emailSenderAdapter.sendEmail()`** | 1. 메서드 실행 시 **어떠한 예외도 외부로 던져지지 않는다.**<br>(`doesNotThrowAnyException`)<br>2. 내부 `try-catch` 블록에서 예외를 잡아 로그를 남기고 정상 종료된다. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **Send (발송)** | 2 | 2 | 0 | 메타데이터 검증 및 예외 처리 검증 완료 |
| **합계** | **2** | **2** | **0** | **Pass** ✅ |

---
**💡 비고:** 메일 본문(Content)의 경우 `MimeMultipart` 구조 분해의 복잡성으로 인해 본 단위 테스트에서는 제외되었으며, 추후 통합 테스트 단계에서 검증할 예정임.