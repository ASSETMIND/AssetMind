# 🏗️ Extractor System Architecture

## 1. 아키텍처 개요 (Overview)

이 시스템은 KIS(한국투자증권), KRX(한국거래소) 등 다양한 금융 데이터 소스로부터 시장 데이터를 수집하는 **Extractor Layer**의 설계를 정의합니다. 핵심 목표는 복잡한 데이터 수집 로직(인증, 통신, 파싱)을 추상화하고, 재시도(Retry)나 유량 제어(Rate Limit)와 같은 횡단 관심사(Cross-cutting Concerns)를 비즈니스 로직과 분리하는 것입니다.

### 🔑 적용된 핵심 디자인 패턴

1.  **Facade Pattern**: `ExtractorService`는 복잡한 추출 하위 시스템(Factory, Extractor, Decorator 조립 등)에 대한 통합된 진입점 역할을 하며, 상위 `PipelineService`와의 결합도를 낮춥니다.
2.  **Factory Method Pattern**: `ExtractorFactory`를 통해 소스 타입(Source Type)에 따른 구체적인 `Extractor` 객체 생성과 의존성 주입(DI) 책임을 위임합니다.
3.  **Template Method Pattern**: `AbstractExtractor`에서 데이터 수집의 표준 알고리즘(검증-인증-요청-파싱)을 정의하고, 세부 구현은 하위 클래스가 확장하도록 합니다.
4.  **Decorator Pattern**: `ExtractorDecorator`를 사용하여 핵심 수집 로직을 수정하지 않고도 **재시도(Retry)**, **유량 제어(Rate Limit)**, **로깅(Logging)** 기능을 동적으로 래핑(Wrapping)하여 확장합니다.
5.  **Strategy Pattern**: `IAuthStrategy`를 통해 OAuth2, API Key 등 상이한 인증 알고리즘을 캡슐화하여 런타임에 교체 가능하도록 설계했습니다.
6.  **Adapter Pattern**: `AsyncHttpAdapter`를 통해 외부 라이브러리(`aiohttp`)를 `IHttpClient` 인터페이스로 변환하여, 도메인 영역이 특정 HTTP 클라이언트 구현에 의존하지 않도록 합니다.
7.  **Singleton Pattern**: `ConfigManager`와 `LogManager`를 통해 설정 정보와 로깅 인스턴스가 시스템 전역에서 유일하게 관리되도록 보장합니다.
8.  **DTO (Data Transfer Object)**: `RequestDTO`와 `ResponseDTO`를 정의하여 계층 간 데이터 교환 규격을 고정하고, 내부 로직 변경이 데이터 구조에 영향을 주지 않도록 합니다.

---

## 2. 클래스 다이어그램 (Class Diagram)

해당 코드를 Mermaid Chart로 구현

```md
---
config:
  look: classic
  theme: redux
  layout: dagre
---

classDiagram
PipelineService --> ExtractorService : Calls (Facade)
ExtractorService --> ExtractorFactory : Uses
ExtractorService ..> IExtractor : Uses Interface

    ExtractorFactory ..> IExtractor : Creates & Assembles
    ExtractorFactory ..> ConfigManager : uses
    IExtractor <|.. AbstractExtractor : Implements
    IExtractor <|.. ExtractorDecorator : Implements
    ExtractorDecorator o-- IExtractor : Wraps
    ExtractorDecorator <|-- RetryDecorator
    ExtractorDecorator <|-- RateLimitDecorator
    ExtractorDecorator <|-- LoggingDecorator
    AbstractExtractor <|-- KISExtractor : Inherits
    AbstractExtractor <|-- KRXExtractor : Inherits
    AbstractExtractor --> IHttpClient :  Uses (Association)
    AbstractExtractor --> IAuthStrategy :  Uses (Strategy)
    IAuthStrategy <|.. OAuth2Strategy : Implements
    IAuthStrategy <|.. APIKeyStrategy : Implements
    IHttpClient <|.. AsyncHttpAdapter
    RateLimitDecorator --> TokenBucketLimiter : Uses
    LoggingDecorator --> LogManager : Uses
    LogManager --> ContextFilter : Uses

    class PipelineService {
        <<Service Layer>>
    }

    namespace Extractor Layer {
        class ExtractorService {
        <<Service Layer>>
        -factory: ExtractorFactory
        +fetch_market_data(ticker, source)
        }

        class ExtractorFactory {
            <<Factory Method>>
            +create_extractor(source_type: Enum) : IExtractor
            -assemble_decorators(core_extractor, config) : IExtractor
        }

        class IExtractor {
            <<Interface>>
            +extract(req: RequestDTO) ResponseDTO
        }

        class AbstractExtractor {
            <<Template Method>>
            #client: IHttpClient
            #auth_strategy: IAuthStrategy
            +extract(params: RequestDTO) : ResponseDTO
            #_validate_params()
            #_prepare_headers()
            #_construct_url()
            #_parse_response()
        }

        class KISExtractor {
            <<Concrete Class>>
            #_construct_url()
            #_parse_response()
        }

        class KRXExtractor {
            <<Concrete Class>>
            #_construct_url()
            #_parse_response()
        }

        class IHttpClient {
            <<Adapter Interface>>
            +get(url, headers)
            +post(url, data, headers)
        }

        class AsyncHttpAdapter {
            <<Concrete Adapter>>
            -session: aiohttp.ClientSession
            +get(url, headers)
            +post(url, data, headers)
        }

        class IAuthStrategy {
            <<Strategy Interface>>
            +get_token() : str
        }

        class OAuth2Strategy
        class APIKeyStrategy

        class ExtractorDecorator {
            <<Decorator Base>>
            -wraps: IExtractor
            +extract(req)
        }

        class RetryDecorator {
            -max_retries: int
            -backoff_factor: float
            +extract(req)
        }

        class RateLimitDecorator {
            -limiter: TokenBucketLimiter
            +extract(req)
        }

        class LoggingDecorator {
            <<Decorator>>
        }

        class TokenBucketLimiter {
            <<Component>>
            +acquire_token()
        }
    }

    namespace Common Layer {
        class LogManager {
            <<Singleton>>
            -logger_instance
            +get_logger(name) : Logger
        }

        class ConfigManager {
            <<Singleton>>
            -config_data: dict
            +load_config(path)
            +get(key, default)
        }

        class ContextFilter {
            <<Component>>
            +inject_context(request_id)
        }
    }
```

## 3. 구성 요소 상세 설명 (Component Details)

### 3.1. Service Layer (Facade & Orchestration)

#### **ExtractorService (Facade)**

- **역할:** 외부 시스템(PipelineService)과 내부의 복잡한 추출 하위 시스템(Factory, Extractors, Decorators) 사이의 **단일 진입점(Entry Point)** 역할을 합니다.
- **설계 의도:** `PipelineService`가 구체적인 Extractor의 생성 과정이나 Decorator의 조립 순서를 알 필요가 없도록 **캡슐화**합니다. 클라이언트는 단순하게 `fetch_market_data(ticker, source)`만 호출하면 되며, 이는 **최소 지식의 원칙(Principle of Least Knowledge)**을 준수합니다.

### 3.2. Core Abstraction & Implementation

#### **IExtractor (Interface)**

- **역할:** 시스템 내 모든 수집기가 반드시 준수해야 하는 최상위 **계약(Contract)**입니다.
- **설계 의도:** Python의 `ABC`(Abstract Base Class)를 사용하여 정의되었습니다.
  - **다형성(Polymorphism):** Decorator와 Concrete Class들이 모두 이 인터페이스를 구현함으로써, 런타임에 객체를 자유롭게 교체하거나 감쌀(Wrap) 수 있는 기반을 제공합니다.
  - **ISP (인터페이스 분리 원칙):** 수집에 필요한 오직 하나의 핵심 동작(`extract`)만을 정의하여 구현체의 불필요한 부담을 제거했습니다.

#### **AbstractExtractor (Base Class / Template)**

- **역할:** 데이터 수집의 불변의 흐름(Skeleton Algorithm)을 제어하고, 중복 코드를 제거합니다.
- **디자인 패턴:** **Template Method Pattern**
- **핵심 로직:** `extract()` 메서드는 `final` 성격으로 정의되어, `검증(_validate) -> 인증 헤더 준비(_prepare) -> URL 생성(_construct) -> HTTP 요청 -> 파싱(_parse)`의 실행 순서를 강제합니다.
- **설계 의도:**
  - **OCP (개방-폐쇄 원칙):** 전체 흐름은 변경하지 않으면서, 상속받는 자식 클래스에서 `_construct_url`과 `_parse_response`만 재정의함으로써 새로운 데이터 소스를 손쉽게 추가할 수 있습니다.

#### **Concrete Extractors (KISExtractor, KRXExtractor)**

- **역할:** 각 데이터 소스(Vendor)에 특화된 비즈니스 로직을 구현합니다.
- **설계 의도:** HTTP 통신이나 인증 토큰 관리와 같은 인프라 로직은 부모 클래스(`AbstractExtractor`)와 전략 객체(`IAuthStrategy`)에 위임하고, 오직 **"어떤 URL을 호출하고, 응답을 어떻게 해석할 것인가"**에만 집중합니다. 이는 **SRP (단일 책임 원칙)**을 철저히 준수한 결과입니다.

### 3.3. Decorator Layer (Cross-Cutting Concerns)

이 계층은 비즈니스 로직(데이터 수집)과 **횡단 관심사(운영 로직)**를 분리하는 핵심적인 역할을 합니다.

#### **ExtractorDecorator (Base)**

- **역할:** `IExtractor`를 구현하면서 동시에 내부에 또 다른 `IExtractor`를 멤버로 가지는(Has-a) 래퍼 클래스입니다.
- **설계 의도:** 상속을 통한 기능 확장보다 유연한 **합성(Composition)**을 사용하여, 런타임에 필요한 기능을 동적으로 조합합니다.

#### **RetryDecorator (Resilience)**

- **역할:** 일시적인 네트워크 장애나 API 서버 오류 시, 지수 백오프(Exponential Backoff) 전략을 사용하여 재시도를 수행합니다.
- **효과:** 불안정한 네트워크 환경에서도 시스템의 **회복 탄력성(Resiliency)**을 보장합니다.

#### **RateLimitDecorator (Throttling)**

- **역할:** `TokenBucketLimiter` 컴포넌트를 사용하여 API 요청 빈도를 제어합니다.
- **설계 의도:** 외부 API의 허용량(Quota) 초과로 인한 IP 차단을 방지합니다. 비즈니스 로직 코드 내에 `time.sleep()`을 섞지 않고, 데코레이터로 분리하여 코드의 순수성을 유지했습니다.

#### **LoggingDecorator (Observability)**

- **역할:** 요청과 응답의 메타데이터, 소요 시간, 성공/실패 여부를 `LogManager`를 통해 기록하여 모니터링 가능성을 확보합니다.

### 3.4. Factory & Creation

#### **ExtractorFactory**

- **역할:** 요청된 소스 타입(Source Type)에 따라 적절한 `Extractor`를 생성하고, 설정(Config)에 따라 필요한 Decorator들을 체이닝(Chaining)하여 반환합니다.
- **디자인 패턴:** **Factory Method Pattern**
- **조립 과정:** 예: `Retry(RateLimit(Logging(KISExtractor)))` 형태의 객체 체인을 조립하여 클라이언트에게 `IExtractor` 타입으로 반환합니다.
- **설계 의도 (DIP):** 객체 생성의 책임을 팩토리로 격리함으로써, 서비스 계층이 구체적인 클래스(`KISExtractor` 등)에 의존하지 않게 합니다.

### 3.5. Infrastructure Layer (Adapters & Strategies)

#### **IHttpClient & AsyncHttpAdapter**

- **역할:** 외부 라이브러리(`aiohttp`)와의 의존성을 격리합니다.
- **디자인 패턴:** **Adapter Pattern**
- **설계 의도:**
  - **테스트 용이성:** 실제 네트워크 통신 없이 `IHttpClient`를 Mocking하여 단위 테스트를 빠르고 안정적으로 수행할 수 있습니다.
  - **유연성:** `aiohttp`에서 `httpx` 등으로 라이브러리를 교체하더라도 도메인 로직은 수정할 필요가 없습니다.

#### **IAuthStrategy (OAuth2, APIKey)**

- **역할:** 데이터 소스마다 상이한 인증 방식을 캡슐화합니다.
- **디자인 패턴:** **Strategy Pattern**
- **설계 의도:** 인증 로직은 변경 빈도가 높고 복잡하므로 별도로 분리했습니다. `AbstractExtractor`는 전략 객체에 인증을 위임할 뿐, 구체적인 방식(OAuth2 vs API Key)은 알 필요가 없습니다.

### 3.6. Common & Utility Layer

#### **LogManager & ContextFilter (Singleton)**

- **역할:** 시스템 전역에서 일관된 로깅 포맷을 제공하고, `ContextFilter`를 통해 요청 ID(Request ID)를 로그에 주입합니다.
- **효과:** 비동기 환경에서 다수의 요청이 혼재될 때, 특정 요청의 흐름을 끝까지 추적(Tracing)할 수 있습니다.

#### **ConfigManager (Singleton)**

- **역할:** 환경 변수(.env)나 설정 파일(yaml)을 로드하여 전역적으로 관리합니다.

### 3.7. Data Transfer Objects (DTO)

#### **RequestDTO / ResponseDTO**

- **역할:** 계층 간(Service <-> Extractor) 데이터를 주고받을 때 사용하는 데이터 규격입니다.
- **구현 기술:** **Pydantic**을 사용하여 런타임 데이터 유효성 검사(Validation)와 타입 안정성을 보장합니다.
- **설계 의도:**
  - **변화 격리:** 외부 API(KIS, KRX)의 응답 필드명이 변경되더라도, 내부 시스템은 항상 동일한 `ResponseDTO` 구조를 사용하도록 `_parse_response`에서 매핑합니다. 이를 통해 외부의 변화가 내부 로직으로 전파되는 것을 차단합니다.

---

## 4. 주요 시나리오 및 실행 흐름 (Key Scenarios & Sequence)

본 시스템은 클라이언트의 요청이 들어왔을 때, 객체를 **런타임에 조립(Runtime Assembly)**하고 실행 흐름을 제어합니다. 대표적인 시나리오인 **"KIS(한국투자증권) 주식 시세 데이터 수집"** 과정을 단계별로 설명합니다.

### 4.1. 정상 처리 흐름 (Normal Success Path)

**1단계: 진입 및 요청 (Entry Point)**

- **Client (PipelineService)**는 구체적인 구현 내용을 모른 채, `ExtractorService.fetch_market_data("Samsung Elec", Source.KIS)`를 호출합니다.
- 이때, 입력 데이터는 `RequestDTO` 형태로 변환되어 타입 안정성을 확보합니다.

**2단계: 객체 생성 및 의존성 주입 (Factory Assembly)**

- `ExtractorService`는 `ExtractorFactory`에게 KIS 타입의 수집기 생성을 요청합니다.
- **Factory**는 다음 순서로 객체를 조립합니다:
  1.  **Core Component:** `KISExtractor`를 생성하고, `AsyncHttpAdapter`(통신)와 `OAuth2Strategy`(인증)를 생성자 주입(DI)합니다.
  2.  **Decoration:** 설정(Config)을 확인하여 Core 객체를 `LoggingDecorator` -> `RateLimitDecorator` -> `RetryDecorator` 순서로 감쌉니다.
- 최종적으로 `IExtractor` 인터페이스 타입으로 서비스 계층에 반환됩니다.

**3단계: 횡단 관심사 처리 (Cross-Cutting Execution)**

- `extract()` 메서드가 호출되면, 가장 바깥쪽의 **RetryDecorator**가 먼저 실행되어 트라이-캐치(Try-Catch) 블록을 설정합니다.
- 그 다음 **RateLimitDecorator**가 `TokenBucket`을 확인하여 요청 가능 여부를 검사합니다. (토큰 부족 시 대기)
- 마지막으로 **LoggingDecorator**가 요청 시작 시간과 메타데이터를 기록합니다.

**4단계: 비즈니스 로직 실행 (Template Method Execution)**

- 데코레이터를 통과한 요청은 **AbstractExtractor**의 `extract()` 템플릿 메서드에 도달합니다.
  1.  `_validate_params()`: 티커 심볼 유효성 등을 검증합니다.
  2.  `_prepare_headers()`: 주입된 **OAuth2Strategy**에게 토큰을 요청합니다. 만료 시 전략 객체 내부에서 자동으로 갱신(Refresh) 후 유효한 토큰을 반환합니다.
  3.  `_construct_url()`: **KISExtractor**(자식 클래스)가 한국투자증권 API 명세에 맞는 URL을 생성합니다.
  4.  `http_client.get()`: **AsyncHttpAdapter**가 실제 비동기 HTTP 요청을 수행합니다.

**5단계: 응답 처리 및 반환 (Parsing & Return)**

- API 응답(JSON)이 도착하면, **KISExtractor**의 `_parse_response()`가 호출되어 원본 데이터를 표준화된 `ResponseDTO`로 변환합니다.
- 호출 스택(Stack)이 풀리면서 로깅 데코레이터가 "성공(Success)" 로그를 남기고, 최종 데이터가 `PipelineService`로 반환됩니다.

---

### 4.2. 장애 대응 및 복구 흐름 (Failure & Recovery Path)

외부 API 서버의 일시적인 오류(500 Internal Server Error) 발생 시의 시나리오입니다.

1.  **오류 감지:** `AsyncHttpAdapter`가 HTTP 500 에러를 수신하고 예외(Exception)를 발생시킵니다.
2.  **전파 차단:** 이 예외는 즉시 클라이언트로 전달되지 않고, 스택 상위에 있는 **RetryDecorator**에 의해 포착(Catch)됩니다.
3.  **지수 백오프(Exponential Backoff):** `RetryDecorator`는 설정된 정책(예: 1초, 2초, 4초 대기)에 따라 잠시 대기한 후, `next_extractor.extract()`를 재호출합니다.
4.  **투명성:** 이 과정에서 내부 `KISExtractor`나 클라이언트 `PipelineService`는 재시도가 일어나는지 알 필요가 없으며(Transparent), 시스템은 스스로 복구를 시도합니다.
5.  **최종 실패:** 최대 재시도 횟수를 초과하면, `LogManager`를 통해 에러 로그를 남기고 최종적으로 사용자 정의 예외(Custom Exception)를 상위로 전파합니다.

---

## 5. 결론 및 기대 효과 (Conclusion & Benefits)

본 Extractor 시스템 아키텍처는 초기 설계 단계에서 구조적인 복잡도를 감수하더라도, 장기적인 **운영 효율성**과 **소프트웨어 품질**을 확보하는 데 초점을 맞추었습니다. **"관심사의 분리(Separation of Concerns)"**와 **"SOLID 원칙"**을 철저히 준수한 이 설계의 기대 효과는 다음과 같습니다.

### 5.1. 기술적 이점 (Technical Advantages)

1.  **무중단 확장성 (OCP 준수):**

    - 새로운 데이터 소스(예: 코인 거래소 Upbit, 해외 주식 Webull 등)가 추가되더라도 기존 코드를 전혀 수정할 필요가 없습니다.
    - 오직 `AbstractExtractor`를 상속받는 새 클래스를 만들고 팩토리에 등록하기만 하면 즉시 확장 가능하며, 이는 회귀 테스트(Regression Test) 범위를 획기적으로 줄여줍니다.

2.  **인프라 종속성 제거 (Dependency Inversion):**

    - **Adapter Pattern**을 통해 `aiohttp`, `requests` 등 특정 라이브러리에 대한 **Vendor Lock-in**을 방지했습니다.
    - 향후 더 나은 성능의 비동기 라이브러리(예: `httpx`)가 등장하더라도, 도메인 로직의 수정 없이 어댑터 교체만으로 기술 스택을 마이그레이션할 수 있습니다.

3.  **높은 회복 탄력성 (Fault Tolerance):**

    - **Decorator Pattern**을 통해 재시도(Retry) 및 유량 제어(Rate Limit) 로직을 중앙에서 일관되게 관리합니다.
    - 개별 개발자가 실수로 예외 처리를 누락하더라도, 시스템 레벨에서 네트워크 불안정에 대한 방어 기제(Safe Guard)가 작동합니다.

4.  **테스트 용이성 (Testability):**
    - 외부 API 통신과 인증 로직이 모두 인터페이스(`IHttpClient`, `IAuthStrategy`)로 추상화되어 있습니다.
    - 실제 네트워크 연결 없이도 `Mock` 객체를 활용하여 100%에 가까운 단위 테스트 커버리지(Code Coverage)를 달성할 수 있으며, 이는 CI/CD 파이프라인의 안정성을 보장합니다.

### 5.2. 결론 (Conclusion)

이 아키텍처는 단순한 데이터 수집 스크립트의 집합이 아닌, **엔터프라이즈급 데이터 파이프라인의 견고한 기반(Foundation)**입니다. 데이터 소스가 기하급수적으로 늘어나고 수집 로직이 복잡해지더라도, 이 시스템은 **낮은 결합도(Low Coupling)**와 **높은 응집도(High Cohesion)**를 유지하며 안정적으로 운영될 것입니다. 이는 결과적으로 **기술 부채(Technical Debt)를 최소화**하고, 새로운 데이터 소스 연동 요구사항에 빠르게 대응하는 **Time-to-Market** 경쟁력을 제공합니다.
