package com.assetmind.server_stock.stock.integration;

import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.*;
import static org.springframework.restdocs.payload.PayloadDocumentation.*;
import static org.springframework.restdocs.request.RequestDocumentation.*;

import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.domain.repository.RawTickRepository;
import com.assetmind.server_stock.stock.domain.repository.StockSnapshotRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import com.assetmind.server_stock.support.IntegrationTestSupport;
import java.time.LocalDateTime;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.mockito.BDDMockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.restdocs.AutoConfigureRestDocs;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.restdocs.mockmvc.RestDocumentationRequestBuilders;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

@Transactional
@AutoConfigureRestDocs
class StockRestApiIntegrationTest extends IntegrationTestSupport {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private StockSnapshotRepository stockSnapshotRepository;

    @Autowired
    private RawTickRepository rawTickRepository;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @MockitoBean
    private StockMetadataProvider stockMetadataProvider;

    @AfterEach
    void tearDown() {
        // 각 테스트 종료시 Redis 저장소 비움
        redisTemplate.getConnectionFactory().getConnection().serverCommands().flushAll();
    }

    @Nested
    @DisplayName("거래 대금 순 랭킹 조회")
    class GetRankingByTradeValue {

        @Test
        @DisplayName("성공: 유효한 Limit으로 조회시 거래대금 내림차순 정렬 데이터와 함께 200 응답 및 문서 생성")
        void givenValidLimit_whenGetRankingByTradeValue_thenRespond200WithData() throws Exception {
            // given
            saveSnapshot("005930", "삼성전자", 1000L, 100L);
            saveSnapshot("000660", "SK하이닉스", 5000L, 50L);

            // when & then
            mockMvc.perform(get("/api/stocks/ranking/value")
                            .param("limit", "10")
                            .accept(MediaType.APPLICATION_JSON))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.success").value(true))
                    .andExpect(jsonPath("$.data[0].stockCode").value("000660")) // 1위 검증

                    // 문서화 로직
                    .andDo(document("stock-ranking/get-value-success",
                            preprocessRequest(prettyPrint()),
                            preprocessResponse(prettyPrint()),
                            queryParameters(
                                    parameterWithName("limit").description("조회할 랭킹 개수 (기본값: 10, 최대: 100)")
                            ),
                            responseFields(
                                    fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("API 호출 성공 여부"),
                                    fieldWithPath("message").type(JsonFieldType.STRING).description("응답 메시지 (성공 시 null)").optional(),

                                    fieldWithPath("data[]").type(JsonFieldType.ARRAY).description("랭킹 데이터 리스트"),
                                    fieldWithPath("data[].stockCode").type(JsonFieldType.STRING).description("종목 코드"),
                                    fieldWithPath("data[].stockName").type(JsonFieldType.STRING).description("종목명"),
                                    fieldWithPath("data[].currentPrice").type(JsonFieldType.STRING).description("현재가"),
                                    fieldWithPath("data[].changeRate").type(JsonFieldType.STRING).description("등락률"),
                                    fieldWithPath("data[].cumulativeAmount").type(JsonFieldType.STRING).description("누적 거래 대금"),
                                    fieldWithPath("data[].cumulativeVolume").type(JsonFieldType.STRING).description("누적 거래량")
                            )
                    ));
        }

        @Test
        @DisplayName("성공: Limit 없이 조회시 기본값 Limit(10)으로 조회되어 200을 응답한다.")
        void givenNoParameter_whenGetRankingByTradeValue_thenRespond200WithData() throws Exception {
            // given: 15개의 더미 데이터 생성
            for (int i = 1; i <= 15; i++) {
                saveSnapshot(String.format("%06d", i), "Stock" + i, (long) i * 100, 10L);
            }

            // when & then
            mockMvc.perform(get("/api/stocks/ranking/value")) // 파라미터 없음
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data.length()").value(10)); // 기본값 10개 확인
        }

        @Test
        @DisplayName("실패: 유효하지 않은 Limit (1 미만) 조회시 400 에러 및 문서 생성")
        void givenInValidLessLimit_whenGetRankingByTradeValue_thenRespond400() throws Exception {
            mockMvc.perform(get("/api/stocks/ranking/value")
                            .param("limit", "0")
                            .accept(MediaType.APPLICATION_JSON))
                    .andExpect(status().isBadRequest())
                    .andDo(document("stock-ranking/get-value-fail-min",
                            preprocessResponse(prettyPrint()),
                            responseFields(
                                    fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("실패 여부 (false)"),
                                    fieldWithPath("message").type(JsonFieldType.STRING).description("에러 상세 메시지"),
                                    fieldWithPath("data").type(JsonFieldType.NULL).description("데이터 (null)").optional()
                            )
                    ));
        }

        @Test
        @DisplayName("실패: 유효하지 않은 Limit (100 초과) 으로 조회시 400을 응답한다.")
        void givenInValidExceedLimit_whenGetRankingByTradeValue_thenRespond400() throws Exception {
            mockMvc.perform(get("/api/stocks/ranking/value")
                            .param("limit", "101"))
                    .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("거래량 순 랭킹 조회")
    class GetRankingByTradeVolume {

        @Test
        @DisplayName("성공: 유효한 Limit으로 조회시 거래량 내림차순으로 정렬된 데이터와 함께 200을 응답한다.")
        void givenValidLimit_whenGetRankingByTradeVolume_thenRespond200WithData() throws Exception {
            // given: 삼성전자가 거래량이 더 높음 (100 > 50)
            saveSnapshot("005930", "삼성전자", 1000L, 100L);
            saveSnapshot("000660", "SK하이닉스", 5000L, 50L);

            // when & then
            mockMvc.perform(get("/api/stocks/ranking/volume")
                            .param("limit", "10"))
                    .andExpect(status().isOk())
                    // [검증] 거래량 1위(삼성전자)가 첫 번째
                    .andExpect(jsonPath("$.data[0].stockCode").value("005930"))
                    .andExpect(jsonPath("$.data[0].cumulativeVolume").value(100))
                    // [검증] 2위(SK하이닉스)
                    .andExpect(jsonPath("$.data[1].stockCode").value("000660"))

                    // 문서화 로직
                    .andDo(document("stock-ranking/get-volume-success",
                    preprocessRequest(prettyPrint()),
                    preprocessResponse(prettyPrint()),
                    queryParameters(
                            parameterWithName("limit").description("조회할 랭킹 개수 (기본값: 10, 최대: 100)")
                    ),
                    responseFields(
                            fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("API 호출 성공 여부"),
                            fieldWithPath("message").type(JsonFieldType.STRING).description("응답 메시지 (성공 시 null)").optional(),

                            fieldWithPath("data[]").type(JsonFieldType.ARRAY).description("랭킹 데이터 리스트"),
                            fieldWithPath("data[].stockCode").type(JsonFieldType.STRING).description("종목 코드"),
                            fieldWithPath("data[].stockName").type(JsonFieldType.STRING).description("종목명"),
                            fieldWithPath("data[].currentPrice").type(JsonFieldType.STRING).description("현재가"),
                            fieldWithPath("data[].changeRate").type(JsonFieldType.STRING).description("등락률"),
                            fieldWithPath("data[].cumulativeAmount").type(JsonFieldType.STRING).description("누적 거래 대금"),
                            fieldWithPath("data[].cumulativeVolume").type(JsonFieldType.STRING).description("누적 거래량")
                    )
            ));
        }

        @Test
        @DisplayName("성공: Limit 없이 조회시 기본값 Limit으로 실제 저장소에서 가져온 데이터와 함께 200을 응답한다.")
        void givenNoParameter_whenGetRankingByTradeVolume_thenRespond200WithData() throws Exception {
            mockMvc.perform(get("/api/stocks/ranking/volume"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.success").value(true));
        }

        @Test
        @DisplayName("실패: 유효하지 않은 Limit (1 미만) 으로 조회시 400을 응답한다.")
        void givenInValidLessLimit_whenGetRankingByTradeVolume_thenRespond400() throws Exception {
            mockMvc.perform(get("/api/stocks/ranking/volume")
                            .param("limit", "-1"))
                    .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("실패: 유효하지 않은 Limit (100 초과) 으로 조회시 400을 응답한다.")
        void givenInValidExceedLimit_whenGetRankingByTradeVolume_thenRespond400() throws Exception {
            mockMvc.perform(get("/api/stocks/ranking/volume")
                            .param("limit", "999"))
                    .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("특정 종목 시계열 데이터 조회")
    class GetStockHistory {

        @Test
        @DisplayName("성공: 유효한 StockCode로 조회시 시계열 데이터 응답 및 문서 생성")
        void givenValidStockCode_whenGetStockHistory_thenRespond200WithData() throws Exception {
            // given
            String stockCode = "005930";
            saveHistory(stockCode, 71000L, LocalDateTime.now());

            BDDMockito.given(stockMetadataProvider.isExist(stockCode)).willReturn(true);

            // when & then
            // PathParameter(StockCode) 문서화를 위해 MockMvcRequestBuilders.get 대신 RestDocumentationRequestBuilders.get 사용
            mockMvc.perform(RestDocumentationRequestBuilders.get("/api/stocks/{stockCode}/history", stockCode)
                            .param("limit", "20")
                            .accept(MediaType.APPLICATION_JSON))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data[0].currentPrice").value("71000.0"))

                    // 문서화 로직
                    .andDo(document("stock-history/get-history-success",
                            preprocessRequest(prettyPrint()),
                            preprocessResponse(prettyPrint()),
                            pathParameters(
                                    parameterWithName("stockCode").description("조회할 종목 코드 (6자리 숫자)")
                            ),
                            queryParameters(
                                    parameterWithName("limit").description("조회할 데이터 개수 (기본값: 20, 최대: 120)")
                            ),
                            responseFields(
                                    fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("성공 여부"),
                                    fieldWithPath("message").type(JsonFieldType.STRING).description("메시지").optional(),

                                    fieldWithPath("data[]").type(JsonFieldType.ARRAY).description("시계열 데이터 리스트"),
                                    fieldWithPath("data[].stockCode").type(JsonFieldType.STRING).description("종목 코드"),
                                    fieldWithPath("data[].currentPrice").type(JsonFieldType.STRING).description("체결가"),
                                    fieldWithPath("data[].openPrice").type(JsonFieldType.STRING).description("시가").optional(),
                                    fieldWithPath("data[].highPrice").type(JsonFieldType.STRING).description("고가").optional(),
                                    fieldWithPath("data[].lowPrice").type(JsonFieldType.STRING).description("저가").optional(),
                                    fieldWithPath("data[].priceChange").type(JsonFieldType.STRING).description("전일 대비 (+1000, -500)").optional(),
                                    fieldWithPath("data[].changeRate").type(JsonFieldType.STRING).description("등락률 (+1.5, -2)").optional(),
                                    fieldWithPath("data[].executionVolume").type(JsonFieldType.STRING).description("체결량"),
                                    fieldWithPath("data[].cumulativeAmount").type(JsonFieldType.STRING).description("누적 거래 대금").optional(),
                                    fieldWithPath("data[].cumulativeVolume").type(JsonFieldType.STRING).description("누적 거래량").optional(),
                                    fieldWithPath("data[].time").type(JsonFieldType.STRING).description("체결 시간 (HHmmss)")
                            )
                    ));
        }

        @Test
        @DisplayName("성공: Limit 없이 조회시 기본값 Limit으로 데이터를 가져오며 200을 응답한다.")
        void givenNoParameter_whenGetStockHistory_thenRespond200WithData() throws Exception {
            // given
            String stockCode = "005930";
            saveHistory(stockCode, 70000L, LocalDateTime.now());

            BDDMockito.given(stockMetadataProvider.isExist(stockCode)).willReturn(true);

            // when & then
            mockMvc.perform(get("/api/stocks/{stockCode}/history", stockCode))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.data").isArray());
        }

        @Test
        @DisplayName("실패: 유효하지 않은 Limit (1 미만) 으로 조회시 400을 응답한다.")
        void givenInValidLessLimit_whenGetStockHistory_thenRespond400() throws Exception {
            mockMvc.perform(get("/api/stocks/005930/history")
                            .param("limit", "0"))
                    .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("실패: 유효하지 않은 Limit (120 초과) 으로 조회시 400을 응답한다.")
        void givenInValidExceedLimit_whenGetStockHistory_thenRespond400() throws Exception {
            mockMvc.perform(get("/api/stocks/005930/history")
                            .param("limit", "121"))
                    .andExpect(status().isBadRequest());
        }
    }

    // 가짜 데이터 생성 헬퍼 메서드
    private void saveSnapshot(String code, String name, Long amount, Long volume) {
        stockSnapshotRepository.save(StockPriceRedisEntity.builder()
                .stockCode(code)
                .stockName(name)
                .cumulativeAmount(amount)
                .cumulativeVolume(volume)
                .build());
    }

    private void saveHistory(String code, Long price, LocalDateTime time) {
        rawTickRepository.save(RawTickJpaEntity.builder()
                .stockCode(code)
                .currentPrice(Double.parseDouble(String.valueOf(price)))
                .volume(10L)
                .priceChange(9.2)
                .tradeTimestamp(time)
                .build());
    }

}
