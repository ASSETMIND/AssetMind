package com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import java.time.LocalTime;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

@ExtendWith(OutputCaptureExtension.class)
class KisOrderBookParserTest {

    private final KisOrderBookParser parser = new KisOrderBookParser();

    @Test
    @DisplayName("성공: KIS 호가 원본 데이터(H0STASP0)를 OrderBook 도메인 객체로 정확히 파싱해야 한다.")
    void givenOrderBookData_whenParse_thenReturnParsedOrderBook() {
        // given
        String stockCode = "005930";
        String marketTime = "093015";

        // KIS 호가 데이터의 일반적인 필드 길이(약 55개)를 가진 가짜 배열 생성 및 "0"으로 초기화
        String[] details = new String[55];
        Arrays.fill(details, "0");
        details[0] = stockCode; // [0] 종목코드
        details[1] = marketTime; // [1] 영업시간

        // 1호가 데이터 세팅 (인덱스 규칙: 매도 3, 매수 13, 매도잔량 23, 매수잔량 33)
        details[3] = "81000";  // 1호가 매도 가격
        details[13] = "80900"; // 1호가 매수 가격
        details[23] = "1500";  // 1호가 매도 잔량
        details[33] = "2000";  // 1호가 매수 잔량

        details[43] = "45000"; // [43] 총 매도 잔량
        details[44] = "38000"; // [44] 총 매수 잔량

        // "^" 기호로 묶어서 진짜 KIS에서 날아오는 형태의 본문 생성
        String rawData = String.join("^", details);
        String payload = "0|H0STASP0|001|" + rawData;

        // when
        List<OrderBook> result = parser.parse(payload);

        // then
        assertThat(result).hasSize(1);
        OrderBook orderBook = result.get(0);

        // 기본 메타데이터 검증
        assertThat(orderBook.stockCode()).isEqualTo("005930");
        assertThat(orderBook.marketTime()).isEqualTo(LocalTime.of(9, 30, 15));
        assertThat(orderBook.totalAskSize()).isEqualTo(45000L);
        assertThat(orderBook.totalBidSize()).isEqualTo(38000L);

        // 10호가 리스트 생성 여부 검증
        assertThat(orderBook.levels()).hasSize(10);

        // 1호가 상세 데이터 맵핑 검증
        OrderBook.Level level1 = orderBook.levels().get(0);
        assertThat(level1.level()).isEqualTo(1);
        assertThat(level1.askPrice()).isEqualTo(81000L);
        assertThat(level1.bidPrice()).isEqualTo(80900L);
        assertThat(level1.askSize()).isEqualTo(1500L);
        assertThat(level1.bidSize()).isEqualTo(2000L);
    }

    @Test
    @DisplayName("성공: 데이터 건수(dataCount)가 생략된 단건 데이터 형식도 정상적으로 파싱해야 한다.")
    void givenNoDataCountOrderBook_whenParse_thenHandleOmittedDataCount() {
        // given (데이터 건수 '001' 자리가 없고 바로 TR_ID 뒤에 본문이 오는 특이 케이스)
        String[] details = new String[55];
        Arrays.fill(details, "0");
        details[0] = "035420";
        details[1] = "153000";
        details[43] = "100";
        details[44] = "200";

        // payload: 0|H0STASP0|035420^153000^...
        String payload = "0|H0STASP0|" + String.join("^", details);

        // when
        List<OrderBook> result = parser.parse(payload);

        // then
        assertThat(result).hasSize(1);
        assertThat(result.get(0).stockCode()).isEqualTo("035420");
        assertThat(result.get(0).marketTime()).isEqualTo(LocalTime.of(15, 30, 0));
    }

    @Test
    @DisplayName("실패: 포맷이 어긋나거나 타입 변환이 불가능한 경우, 에러를 로깅하고 빈 리스트를 반환해야 한다.")
    void givenInvalidOrderBook_whenParse_thenShouldCatchExceptionAndLogging(CapturedOutput output) {
        // given: 시간(HHmmss)이 들어가야 할 자리에 문자열이 섞인 악의적인 데이터
        String payload = "0|H0STASP0|001|005930^WRONG_TIME^0^81000";

        // when
        List<OrderBook> result = parser.parse(payload);

        // then: 시스템이 죽지 않고 빈 리스트를 반환
        assertThat(result).isEmpty();

        // 로그에 에러 메시지가 정상적으로 찍혔는지 확인
        assertThat(output.getOut()).contains("KIS 실시간 호가 데이터 파싱 중 오류 발생");
    }
}
