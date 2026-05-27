package com.assetmind.server_stock.stock.presentation;

import static org.mockito.BDDMockito.*;
import static org.springframework.restdocs.mockmvc.RestDocumentationRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.stock.application.OrderBookService;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import java.time.LocalTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.restdocs.AutoConfigureRestDocs;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(OrderBookController.class)
@AutoConfigureRestDocs
public class OrderBookControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private OrderBookService orderBookService;

    @Test
    @DisplayName("종목 코드로 해당 종목의 호가 조회 시, 데이터가 존재하면 데이터를 담아 응답한다.")
    void givenValidStockCode_whenGetOrderBookSnapshot_thenSuccess200AndData() throws Exception {
        // given
        String stockCode = "005930";
        OrderBook dummyOrderBook = OrderBook.builder()
                .stockCode(stockCode)
                .marketTime(LocalTime.of(15, 30, 0))
                .totalBidSize(1500L)
                .totalAskSize(2000L)
                .levels(List.of())
                .build();

        given(orderBookService.getOrderBookSnapshot(stockCode)).willReturn(dummyOrderBook);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/orderbook", stockCode))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.stockCode").value(stockCode))
                .andExpect(jsonPath("$.data.totalBidSize").value(1500L));

    }

    @Test
    @DisplayName("종목 코드로 해당 종목의 호가 조회 시, 데이터가 존재하지 않으면 빈 데이터를 응답한다.")
    void givenValidStockCode_whenGetOrderBookSnapshotIfNonData_thenSuccess200AndNull()
            throws Exception {
        // given
        String stockCode = "005930";
        given(orderBookService.getOrderBookSnapshot(stockCode)).willReturn(null);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/orderbook", stockCode)
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("해당 종목의 호가 스냅샷이 존재하지 않습니다."))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("지원하지 않는 종목 코드로 해당 종목의 호가 조회 시, 400 에러를 응답한다.")
    void givenInvalidStockCOde_whenGetOrderBookSnapshot_thenBadRequest400() throws Exception {
        // given
        String invalidStockCode = "123";
        // 서비스 계층에서 예외를 던지도록 스터빙
        given(orderBookService.getOrderBookSnapshot(invalidStockCode))
                .willThrow(new InvalidStockParameterException("유효하지 않은 종목 코드입니다.", ErrorCode.INVALID_STOCK_PARAMETER));

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/orderbook", invalidStockCode)
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(ErrorCode.INVALID_STOCK_PARAMETER.getMessage()));
    }
}
