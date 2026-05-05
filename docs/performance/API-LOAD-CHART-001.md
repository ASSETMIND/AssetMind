| 문서 ID     | API-LOAD-CHART-001 |
|:----------|:-------------------|
| **문서 버전** | 1.0                |
| **프로젝트**  | AssetMind          |
| **작성자**   | 이재석                |
| **작성일**   | 2026년 05월 05일      |

# 차트 조회 API, DB의 부하를 분산시켜 성능 개선시키기

# 1. 문제 상황

특정 종목의 차트를 조회하는 API를 만들고 나서 K6를 이용해 부하 테스트를 진행했다.

부하 테스트는 초기에는 VU를 50명에서 점차 200명, 500명으로 늘리고 해당 VU가 차트 페이지를 5페이지까지 무한 스크롤 하는 상황을 연출했다.

![result-1](https://github.com/user-attachments/assets/bc2519f9-300c-48d3-a2c5-7101249edbba)

### 결과

- **p(95) 응답 시간:** 52.32초
- **TPS:** 7.43
- **에러율:** 5.52%

결과가 이렇다는 것은 유저가 특정 종목의 사이트를 들어갔을 때 52초가 지나서 차트를 볼 수 있다는 것인데, 그 어떤 유저도 이렇게 느려터지고 에러률이 5.52%나 되는 서비스를 이용할 유저는 없기 때문에 아주 심각한 문제라고 볼 수 있다.

# 2. 원인 분석

차트 조회하는데 52초나 걸리는 문제를 해결하기 위해서 Prometheus로 지표를 수집하고 Grafana로 그래프를 그린 모니터링 환경에서 그래프 지표를 확인했다.

![result-2](https://github.com/user-attachments/assets/35822763-8296-4ee6-b507-724193dff7fb)

![result-3](https://github.com/user-attachments/assets/8f4343c2-608a-47e1-9b43-f4d622b16b0d)

Spring에서 사용하고 있는 HikariCP의 기본값인 10개의 커넥션을 모두 사용하고 Pending 상태의 WAS 스레드들이 최대 191개 까지 생기는 것을 확인할 수 있다.

그래서 차트 조회에 사용되는 `ChartService` 와 `Ohlcv1mJpaAdapter` 두 개의 실행 시간 로그를 찍어보니 `ChartService` 의 실행시간은 **1ms**에 끝나게 되고, ****`Ohlcv1mJpaAdapter` 의 실행시간이 차트 조회 API 성능을 저하시킨다는 것을 확인할 수 있었다.

원인 분석을 해보니, DB 조회 쿼리 실행 시간이 너무 오래걸리니까 Connection Pool을 그만큼 오래 점유하게 되고 트래픽이 많아짐에 따라 DB Connection Pool이 고갈되어 P(95)는 52.32s 가 나오고, TPS는 1초당 7개, 에러률은 5.52%라는 결과가 나온다는 것을 알게되었다.

그러면 도대체 쿼리의 어떤 부분이 문제였을까?

```sql
SELECT 
    date_bin(CAST(:intervalString AS INTERVAL), candle_timestamp, TIMESTAMP '2000-01-01') AS candleTimestamp,
    (array_agg(open_price ORDER BY candle_timestamp ASC))[1] AS open,
    MAX(high_price) AS high,
    MIN(low_price) AS low,
    (array_agg(close_price ORDER BY candle_timestamp DESC ))[1] AS close,
    SUM(volume) AS volume
FROM ohlcv_1m
WHERE stock_code = :stockCode AND candle_timestamp <= :endTime
GROUP BY candleTimestamp
ORDER BY candleTimestamp DESC
LIMIT :limit
```

사용자가 N분봉을 요청하게 되면 DB단에서 1분봉을 토대로 `GROUP BY` 와 `date_bin` 을 통해 N분봉으로 롤업하여 응답하였다. 하지만 이 쿼리에는 치명적인 문제가 있었다.

첫 번째 문제는 불필요한 전체 범위 스캔이었다.  `WHERE stock_code = :stockCode AND candle_timestamp <= :endTime` 조건으로 인해 endTime이 오늘이라면, 2001-01-01 부터 오늘까지 쌓인 수많은 1분봉 데이터를 스캔해야되는 문제가 발생한다.

두 번째 문제는 DB는 이 방대한 데이터를 스캔한 뒤 무거운 그룹화 연산을 수행하고, 그 안에서 `array_agg`로 내부 정렬까지 거쳐 전체 차트 리스트를 완성하지만 결국 마지막에 `LIMIT` 개수만큼만 잘라내어 반환하고, 나머지 데이터는 그대로 날리는 매우 비효율적인 쿼리였다.

# 3. 문제 해결

원인 분석을 하고, 기존의 병목을 해결하기 위해 1분봉 데이터를 N분봉으로 집계하는 책임을 어디에 둘 것인지 두 가지 선택지를 놓고 고민했다.

**선택지 A: DB 단에서 집계 유지 + 쿼리 튜닝 → 기존 방식 개선**

- **방식**: DB에서 `GROUP BY` , `date_bin` 과 같은 집계 함수를 사용하되 병목에 제일 큰 문제가 되는 풀스캔을 막기 위해 서브 쿼리 등을 활용하여 조회 범위를 제한하는 방식
- **장점**
    - 집계된 결과만 반환되기 때문에 WAS(Spring)로 전송되는 네트워크 데이터 양이 가장 적음
    - 애플리케이션 계층(`ChartService`)의 로직이 단순해짐
- **단점**
    - `PostgreSQL` 특화 함수인 `date_bin` 을 피하기 어렵고, 여전히 쿼리가 내 수준에 비해 매우 복잡하여 유지보수성이 떨어짐
    - 트래픽이 더 급증하게 됐을 때, WAS(Spring)는 스케일 아웃이 쉽지만, RDBMS는 스케일 아웃 비용이 매우 크고 어려움

**선택지 B: 단순 조회 후 WAS(Spring)에서 집계 처리**

- 방식: DB에서는 필요한 1분봉 데이터만 단순 조회하고, 무거운 병합 연산은 `ChartService` 에 위임하는 방식
- 장점
    - DB의 역할을 연산이 아닌 검색으로만 제한하여 DB 커넥션 유지 시간과 DB 메모리 부하를 매우 낮출 수 있음
    - 복잡한 연산 부하를 스케일 아웃이 쉬운 WAS(Spring)으로 넘겨, 향후 대규모 트래픽 대응에 유리함
    - 특정 DB에 종속된 Native Query를 제거하고 순수 JPA(JPQL)로 추상화하여, 추후 RDBMS 변경에 유연한 아키텍처를 가질 수 있음
- 단점
    - DB에서 WAS로 가져오는 데이터 양이 `선택지 A` 보다 상대적으로 증가. 예를 들어 5분봉 20개를 위해서는 1분봉 100개를 가져와야함

이해하기 어려운 쿼리에서 스캔 범위를 개선하는 방식(`선택지 A`)보다 비용이 비싼 DB 자원을 아끼고 아키텍처의 유연성 및 유지보수성을 확보하는 `선택지 B` 방식을 채택했다.

클라이언트가 요청한 N분봉 개수를 역산(예: 5분봉 20개 -> 1분봉 100개 필요)하여 DB에는 `LIMIT 100` 조건만 넘겨 스캔 범위를 최소화하고, `ChartService`에서 비즈니스 로직으로 데이터를 롤업하는 구조로 아키텍처를 개편했다.

# 4. 개선 결과

기존 병목이 발생했던 상황과 동일하게, 부하 테스트는 초기에는 VU를 50명에서 점차 200명, 500명으로 늘리고 해당 VU가 차트 페이지를 5페이지까지 무한 스크롤 하는 상황을 연출했다.

![result-4](https://github.com/user-attachments/assets/0d8db84f-6ba4-4a7d-9495-4febb32df66b)

### 결과

- **P(95) 응답 시간:** 52.32s → 42.21ms
- **TPS :** 약 7/s → 약 153/s
- **에러률:** 5.52% → 0%

![result-5](https://github.com/user-attachments/assets/efd92c9b-2330-473d-aff1-ccc9298f1fb2)

![result-6](https://github.com/user-attachments/assets/7fe71c6d-1319-447f-97a5-c8d244d5eba9)

DB Connection Pool도 부하 테스트 도중 Pending 상태 없이 안정적인 속도로 검색하고 있다는 것을 확인할 수 있다. DB I/O 부하를 획기적으로 낮추고 스케일 아웃이 쉬운 WAS로 연산을 분산하여, 극심한 트래픽 환경에서 안정적인 응답속도를 달성했다.

# 5. 회고

흔히 성능 문제가 발생하면 습관적으로 Redis와 같은 캐싱 인프라 도입을 먼저 떠올리곤 했었다. 하지만 이번 경험을 통해, 무작정 새로운 인프라를 추가하기 전에 아키텍처의 책임을 올바르게 분리하는 것이 성능 최적화의 진정한 첫걸음임을 깨달았다.

또한, 로직의 책임을 DB에서 WAS로 완전히 뒤엎는 대규모 리팩토링이었음에도 불구하고, 미리 작성해 둔 통합 테스트 코드 덕분에 비즈니스 로직(차트 가격 정합성)이 깨지지 않음을 확신하며 자신감 있게 개선을 마칠 수 있었다.