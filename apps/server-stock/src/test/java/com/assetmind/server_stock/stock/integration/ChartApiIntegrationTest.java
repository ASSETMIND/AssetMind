package com.assetmind.server_stock.stock.integration;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import com.assetmind.server_stock.support.IntegrationTestSupport;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

public class ChartApiIntegrationTest extends IntegrationTestSupport {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private Ohlcv1mRepository ohlcv1mRepository;

    @Test
    @DisplayName("API 요청 시, 실제 DB 네이티브 쿼리가 동작하여 동적 롤업된 차트 데이터가 반환된다.")
    void givenValidRequest_whenGetCandles_thenResponseRollupData() throws Exception {
        // given
        String stockCode = "005930";
        LocalDateTime baseTime = LocalDateTime.of(2000, 1, 1, 9, 0);

        ohlcv1mRepository.saveAll(List.of(
                // 09:00 (시가 100, 고가 120, 저가 90, 종가 110, 거래량 10)
                new OhlcvDto(stockCode, baseTime, 100.0, 120.0, 90.0, 110.0, 10L),
                // 09:01 (시가 110, 고가 150, 저가 100, 종가 140, 거래량 20)
                new OhlcvDto(stockCode, baseTime.plusMinutes(1), 110.0, 150.0, 100.0, 140.0, 20L),
                // 09:02 (시가 140, 고가 160, 저가 80, 종가 155, 거래량 30)
                new OhlcvDto(stockCode, baseTime.plusMinutes(2), 140.0, 160.0, 80.0, 155.0, 30L)
        ));

        // when: 프론트엔드라고 가정하고 3분봉(3m) 데이터를 요청
        LocalDateTime endTime = LocalDateTime.of(2000, 1, 1, 9, 5); // 09:05 이전 데이터 요청

        mockMvc.perform(get("/api/stocks/{stockCode}/charts/candles", stockCode)
                        .param("timeframe", "3m")
                        .param("limit", "10")
                        .param("endTime", endTime.toString())
                        .accept(MediaType.APPLICATION_JSON))
                .andDo(print())


        // then: HTTP API부터 DB 집계까지 파이프라인이 완벽히 동작했는지 검증

                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.stockCode").value(stockCode))
                .andExpect(jsonPath("$.data.timeframe").value("3m"))
                .andExpect(jsonPath("$.data.candles.length()").value(1)) // 3개의 1분봉이 1개의 3분봉으로 묶였어야 함!

                // 3분봉 롤업이 잘 동작하는지 검증
                .andExpect(jsonPath("$.data.candles[0].timestamp").value("2000-01-01T09:00:00"))
                .andExpect(jsonPath("$.data.candles[0].open").value(100.0))   // 09:00의 시가
                .andExpect(jsonPath("$.data.candles[0].high").value(160.0))   // 3분 중 최고가
                .andExpect(jsonPath("$.data.candles[0].low").value(80.0))     // 3분 중 최저가
                .andExpect(jsonPath("$.data.candles[0].close").value(155.0))  // 09:02의 종가
                .andExpect(jsonPath("$.data.candles[0].volume").value(60L));  // 거래량 총합 (10+20+30)
    }

    @Test
    @DisplayName("필수 파라미터(timeframe)가 누락되면 400 에러와 함께 fail 응답을 반환한다.")
    void givenNullTimeframe_whenGetCandles_thenResponse400Error() throws Exception {
        // given: timeframe 없이 요청을 보냄
        String stockCode = "005930";

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/charts/candles", stockCode)
                        .param("limit", "10"))
                .andDo(print())
                .andExpect(status().isBadRequest()) // 400 확인
                .andExpect(jsonPath("$.success").value(false)) // ApiResponse.fail() 구조 확인
                .andExpect(jsonPath("$.message").exists()); // 에러 메시지가 존재하는지 확인
    }

    @Test
    @DisplayName("지원하지 않는 타임프레임(99m) 요청 시 400 에러를 반환한다.")
    void givenInvalidTimeframe_whenGetCandles_thenResponse400Error() throws Exception {
        // given
        String stockCode = "005930";

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/charts/candles", stockCode)
                        .param("timeframe", "99m") // 지원하지 않는 형식
                        .param("limit", "10"))
                .andDo(print())
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }
}
