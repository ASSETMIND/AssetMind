# Test Specification: Abstract Extractor

## 1. 개요

- **Target Module:** `data_collection.extraction.abstract_extractor.AbstractExtractor`
- **Objective:** 설정 주도 ETL 파이프라인의 제어 흐름 및 예외 정책 검증.

## 2. 테스트 환경

- **Implementation:** `ConcreteMockExtractor` (추상 클래스 테스트용)
- **Mocking:** `IHttpClient`, `AppConfig`, `Logger`

## 3. 테스트 케이스 명세

|  Test ID   | Category  | Given (Preconditions)                  | When (Action)                            | Then (Expected Outcome)                                               | Input Data              |
| :--------: | :-------: | :------------------------------------- | :--------------------------------------- | :-------------------------------------------------------------------- | :---------------------- |
| **TC-001** |   Unit    | 정상적인 Client, Config, 구현체 준비됨 | `extract(request)` 호출                  | 1. `_validate` -> `_fetch` -> `_create` 실행<br>2. `ResponseDTO` 반환 | `RequestDTO("valid")`   |
| **TC-002** |   Unit    | `extract` 실행 준비됨                  | `extract(request)` 호출                  | 시작 및 종료 `logger.info` 기록                                       | `RequestDTO("valid")`   |
| **TC-003** |   Unit    | `config`가 `None`인 상황               | `AbstractExtractor(client, None)` 생성   | `ExtractorError` 발생 (초기화 실패)                                   | `config=None`           |
| **TC-004** |   Unit    | 유효한 `client`와 `config` 준비됨      | `AbstractExtractor(client, config)` 생성 | 정상 생성 및 `self.config` 주입 확인                                  | `AppConfig(...)`        |
| **TC-005** | Exception | `request` 객체가 `None`                | `extract(None)` 호출                     | `ExtractorError`로 래핑되어 발생                                      | `request=None`          |
| **TC-006** | Boundary  | `_fetch`가 `None` 반환                 | `extract(request)` 호출                  | 에러 없이 `_create(None)` 호출                                        | `Fetch returns None`    |
| **TC-007** | Exception | `_validate`에서 `ExtractorError` 발생  | `extract(request)` 호출                  | 1. `ExtractorError` 재발생 (Re-raise)<br>2. `_fetch` 미실행 확인      | `RequestDTO("invalid")` |
| **TC-008** | Exception | `_fetch` 중 `NetworkError` 발생        | `extract(request)` 호출                  | `ExtractorError`로 변환 발생 (Chaining)                               | `NetworkError(...)`     |
| **TC-009** | Exception | `_create` 중 `ExtractorError` 발생     | `extract(request)` 호출                  | `ExtractorError` 재발생 (Re-raise)                                    | `ExtractorError(...)`   |
| **TC-010** | Exception | `_fetch` 중 `ValueError` (버그) 발생   | `extract(request)` 호출                  | `ExtractorError`로 래핑 및 Stack Trace 기록                           | `ValueError(...)`       |
| **TC-011** | Resource  | `extract` 실행 완료                    | Config 객체 상태 확인                    | 실행 전후 Config 객체 불변성 검증                                     | `RequestDTO("valid")`   |
| **TC-012** |   Unit    | `_validate` 성공 설정                  | `extract(request)` 호출                  | `_validate` 직후 `_fetch` 호출 순서 검증                              | `RequestDTO("valid")`   |
