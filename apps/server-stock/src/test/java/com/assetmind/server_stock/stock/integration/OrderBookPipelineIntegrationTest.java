package com.assetmind.server_stock.stock.integration;

import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.support.IntegrationTestSupport;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.market_access.domain.event.OrderBookReceivedEvent;
import java.time.LocalTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.BDDMockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

public class OrderBookPipelineIntegrationTest extends IntegrationTestSupport {

    @Autowired
    private MockMvc mockMvc;

    // KIS 어댑터를 대신하여 이벤트를 허공에 쏴줄 퍼블리셔
    @Autowired
    private ApplicationEventPublisher eventPublisher;

    @MockitoBean
    private StockMetadataProvider stockMetadataProvider;

    @Test
    @DisplayName("KIS 호가 수신 -> 이벤트 리스너 -> 캐시 저장 -> REST API 즉시 조회 성공")
    void givenKisFileEvent_whenGetOrderBook_thenServeLatestSnapshot() throws Exception {
        // given
        String stockCode = "005930"; // 삼성전자
        OrderBook incomingOrderBook = OrderBook.builder()
                .stockCode(stockCode)
                .marketTime(LocalTime.of(9, 1, 30))
                .totalBidSize(10000L)
                .totalAskSize(20000L)
                .levels(List.of()) // 실제로는 호가 리스트가 들어가야 함
                .build();

        BDDMockito.given(stockMetadataProvider.isExist(stockCode)).willReturn(true);

        // ==========================================
        // 수집: KIS에서 데이터가 들어왔다고 가정하고 이벤트를 강제 발행!
        // ==========================================
        eventPublisher.publishEvent(new OrderBookReceivedEvent(incomingOrderBook));

        // (내부 동작: 리스너가 동기로 캐치 -> ConcurrentHashMap 에 save)

        // ==========================================
        // 서빙: 프론트엔드가 진입해서 API 단건 조회
        // ==========================================
        mockMvc.perform(get("/api/stocks/{stockCode}/orderbook", stockCode)
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                // 검증: 발행했던 데이터가 그대로 나오는지 확인
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.stockCode").value(stockCode))
                .andExpect(jsonPath("$.data.totalBidSize").value(10000L))
                .andExpect(jsonPath("$.data.totalAskSize").value(20000L));
    }

    @Test
    @DisplayName("KIS 호가가 한 번도 수신되지 않은 장 시작 전 상태에서의 API 조회")
    void givenNoEventPublished_whenGetOrderBook_thenReturnEmptyData() throws Exception {
        // given
        String newStockCode = "000660";

        BDDMockito.given(stockMetadataProvider.isExist(newStockCode)).willReturn(true);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/orderbook", newStockCode)
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("해당 종목의 호가 스냅샷이 존재하지 않습니다."))
                .andExpect(jsonPath("$.data").isEmpty());
    }
}
