package com.assetmind.server_stock.stock.presentation;

import static org.mockito.BDDMockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.assetmind.server_stock.global.error.GlobalExceptionHandler;
import com.assetmind.server_stock.stock.application.StockService;
import com.assetmind.server_stock.stock.presentation.dto.StockHistoryResponse;
import com.assetmind.server_stock.stock.presentation.dto.StockRankingResponse;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(StockController.class)
@Import(GlobalExceptionHandler.class)
class StockControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private StockService stockService;

    @Test
    @DisplayName("성공: [GET] 거래 대금 순 랭킹 조회, 유효한 Limit 값으로 조회를 하면 200 응답과 함께 데이터를 응답한다.")
    void givenValidLimit_whenGetRankingByTradeValue_thenRespond200() throws Exception {
        // given
        List<StockRankingResponse> mockResponse = List.of(
                StockRankingResponse.builder()
                        .stockCode("005930")
                        .stockName("삼성전자")
                        .currentPrice("80000")
                        .changeRate("1.5")
                        .cumulativeAmount("1000000")
                        .cumulativeVolume("50000")
                        .build()
        );

        given(stockService.getTopStocksByTradeValue(10)).willReturn(mockResponse);

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/value")
                        .param("limit", "10")
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print()) // 로그 출력
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].stockCode").value("005930"))
                .andExpect(jsonPath("$.data[0].stockName").value("삼성전자"));
    }

    @Test
    @DisplayName("실패: [GET] 거래 대금 순 랭킹 조회, 유효하지 않은 Limit 값(1 미만)으로 조회를 하면 형식 오류 예외 (400)를 응답한다.")
    void givenInvalidLessLimit_whenGetRankingByTradeValue_thenRespond400() throws Exception {
        // given (Service는 호출되지 않음)

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/value")
                        .param("limit", "0") // @Min(1) 위반
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isBadRequest())

                // GlobalExceptionHandler가 반환하는 JSON 구조 확인 (code, message 등)
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [GET] 거래 대금 순 랭킹 조회, 유효하지 않은 Limit 값(100 초과)으로 조회를 하면 형식 오류 예외 (400)를 응답한다.")
    void givenInvalidExceedLimit_whenGetRankingByTradeValue_thenRespond400() throws Exception {
        // given (Service는 호출되지 않음)

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/value")
                        .param("limit", "101") // @Max(100) 위반
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isBadRequest())

                // GlobalExceptionHandler가 반환하는 JSON 구조 확인 (code, message 등)
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("성공: [GET] 거래 대금 순 랭킹 조회, 파라미터가 없으면 디폴트(10)로 동작하며 200 응답을 한다.")
    void givenNoLimitParam_whenGetRankingByTradeValue_thenUseDefaultAndRespond200() throws Exception {
        // given
        given(stockService.getTopStocksByTradeValue(10)).willReturn(List.of()); // 빈 리스트 반환 가정

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/value")) // param 없음
                .andDo(print())
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("성공: [GET] 거래량 순 랭킹 조회, 유효한 Limit 값으로 조회를 하면 200 응답과 함께 데이터를 응답한다.")
    void givenValidLimit_whenGetRankingByTradeVolume_thenRespond200() throws Exception {
        // given
        List<StockRankingResponse> mockResponse = List.of(
                StockRankingResponse.builder()
                        .stockCode("005930")
                        .stockName("삼성전자")
                        .currentPrice("80000")
                        .changeRate("1.5")
                        .cumulativeAmount("1000000")
                        .cumulativeVolume("50000")
                        .build()
        );

        given(stockService.getTopStocksByTradeVolume(10)).willReturn(mockResponse);

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/volume")
                        .param("limit", "10")
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print()) // 로그 출력
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].stockCode").value("005930"))
                .andExpect(jsonPath("$.data[0].stockName").value("삼성전자"));
    }

    @Test
    @DisplayName("실패: [GET] 거래량 순 랭킹 조회, 유효하지 않은 Limit 값(1 미만)으로 조회를 하면 형식 오류 예외 (400)를 응답한다.")
    void givenInvalidLessLimit_whenGetRankingByTradeVolume_thenRespond400() throws Exception {
        // given (Service는 호출되지 않음)

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/volume")
                        .param("limit", "0") // @Min(1) 위반
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isBadRequest())

                // GlobalExceptionHandler가 반환하는 JSON 구조 확인 (code, message 등)
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [GET] 거래량 순 랭킹 조회, 유효하지 않은 Limit 값(100 초과)으로 조회를 하면 형식 오류 예외 (400)를 응답한다.")
    void givenInvalidExceedLimit_whenGetRankingByTradeVolume_thenRespond400() throws Exception {
        // given (Service는 호출되지 않음)

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/volume")
                        .param("limit", "101") // @Max(100) 위반
                        .contentType(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isBadRequest())

                // GlobalExceptionHandler가 반환하는 JSON 구조 확인 (code, message 등)
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("성공: [GET] 거래량 순 랭킹 조회, 파라미터가 없으면 디폴트(10)로 동작하며 200 응답을 한다.")
    void givenNoLimitParam_whenGetRankingByTradeVolume_thenUseDefaultAndRespond200() throws Exception {
        // given
        given(stockService.getTopStocksByTradeVolume(10)).willReturn(List.of()); // 빈 리스트 반환 가정

        // when & then
        mockMvc.perform(get("/api/stocks/ranking/volume")) // param 없음
                .andDo(print())
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("성공: [GET] 특정 종목 시계열 데이터 조회")
    void givenValidStockCodeAndLimit_whenGetStockHistory_thenRespond200() throws Exception {
        // given
        List<StockHistoryResponse> mockResponse = List.of(
                StockHistoryResponse.builder()
                        .stockCode("005930")
                        .currentPrice("80000")
                        .time("120000")
                        .build()
        );

        given(stockService.getStockRecentHistory("005930", 50)).willReturn(mockResponse);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/history", "005930")
                        .param("limit", "50"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].stockCode").value("005930"));
    }

    @Test
    @DisplayName("실패: [GET] 특정 종목 시계열 데이터 조회, 유효하지 않은 Limit 값(1 미만)으로 조회를 하면 형식 오류 예외 (400)를 응답한다.")
    void givenInvalidLessLimit_whenGetStockHistory_thenRespond400() throws Exception {
        // given (Service는 호출되지 않음)

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/history", "005930")
                        .param("limit", "0")) // @Min(1) 위반
                .andDo(print())
                .andExpect(status().isBadRequest())

                // GlobalExceptionHandler가 반환하는 JSON 구조 확인 (code, message 등)
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [GET] 특정 종목 시계열 데이터 조회, 유효하지 않은 Limit 값(120 초과)으로 조회를 하면 형식 오류 예외 (400)를 응답한다.")
    void givenInvalidExceedLimit_whenGetStockHistory_thenRespond400() throws Exception {
        // given (Service는 호출되지 않음)

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/history", "005930")
                        .param("limit", "121")) // @Max(120) 위반
                .andDo(print())
                .andExpect(status().isBadRequest())

                // GlobalExceptionHandler가 반환하는 JSON 구조 확인 (code, message 등)
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").exists())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("실패: [GET] 특정 종목 시계열 데이터 조회, StockCode가 공백이면 400 에러를 응답한다.")
    void givenInvalidStockCodeAndLimit_whenGetStockHistory_thenRespond400() throws Exception {
        // given

        // when & then
        mockMvc.perform(get("/api/stocks/ /history") // 종목 코드 공백 URL
                        .param("limit", "50"))
                .andDo(print())
                .andExpect(status().isBadRequest()); // @NotBlank 위반
    }

    @Test
    @DisplayName("성공: [GET] 특정 종목 시계열 데이터 조회, 파라미터가 없으면 디폴트(50)로 동작하며 200 응답을 한다.")
    void givenNoLimitParam_whenGetStockHistory_thenUseDefaultAndRespond200() throws Exception {
        // given
        List<StockHistoryResponse> mockResponse = List.of(
                StockHistoryResponse.builder()
                        .stockCode("005930")
                        .currentPrice("80000")
                        .time("120000")
                        .build()
        );

        given(stockService.getStockRecentHistory("005930", 30))
                .willReturn(mockResponse);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/history", "005930"))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].stockCode").value("005930"));

    }
}