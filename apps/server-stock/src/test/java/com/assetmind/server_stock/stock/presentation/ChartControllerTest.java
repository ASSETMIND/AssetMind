package com.assetmind.server_stock.stock.presentation;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.mockmvc.RestDocumentationRequestBuilders.get;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessRequest;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessResponse;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.prettyPrint;
import static org.springframework.restdocs.payload.PayloadDocumentation.fieldWithPath;
import static org.springframework.restdocs.payload.PayloadDocumentation.responseFields;
import static org.springframework.restdocs.request.RequestDocumentation.parameterWithName;
import static org.springframework.restdocs.request.RequestDocumentation.pathParameters;
import static org.springframework.restdocs.request.RequestDocumentation.queryParameters;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.assetmind.server_stock.stock.application.ChartService;
import com.assetmind.server_stock.stock.presentation.dto.ChartResponseDto;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.restdocs.AutoConfigureRestDocs;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ChartController.class)
@AutoConfigureRestDocs
class ChartControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ChartService chartService;

    @Test
    @DisplayName("[성공] 차트 캔들 조회 성공 및 REST Docs 생성")
    void givenInvalidData_whenGetCandles_thenSuccess200() throws Exception {
        // given
        String stockCode = "005930";
        String timeframe = "5m";
        int limit = 10;
        LocalDateTime endTime = LocalDateTime.of(2026, 4, 1, 10, 0);

        ChartResponseDto.CandleDto candle = ChartResponseDto.CandleDto.builder()
                .timestamp(endTime)
                .open("80000.0")
                .high("81000.0")
                .low("79000.0")
                .close("80500.0")
                .volume("1000")
                .build();

        ChartResponseDto responseDto = ChartResponseDto.builder()
                .stockCode(stockCode)
                .timeframe(timeframe)
                .candles(List.of(candle))
                .build();

        given(chartService.getCandles(eq(stockCode), eq(timeframe), eq(endTime), eq(limit)))
                .willReturn(responseDto);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/charts/candles", stockCode)
                        .param("timeframe", timeframe)
                        .param("limit", String.valueOf(limit))
                        .param("endTime", endTime.toString())
                        .accept(MediaType.APPLICATION_JSON))
                .andDo(print())
                .andExpect(status().isOk())
                // 💡 ApiResponse 필드 검증
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").isEmpty())
                // 💡 ApiResponse 내부 data(ChartResponseDto) 필드 검증
                .andExpect(jsonPath("$.data.stockCode").value(stockCode))
                .andExpect(jsonPath("$.data.candles[0].close").value(80500.0))

                .andDo(document("chart-get-candles",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        pathParameters(
                                parameterWithName("stockCode").description("주식 종목 코드 (6자리 숫자)")
                        ),
                        queryParameters(
                                parameterWithName("timeframe").description("차트 타임프레임 (예: 1m, 5m, 1d, 1mo)"),
                                parameterWithName("limit").description("조회할 캔들 개수 (기본값 200, 최대 1000)").optional(),
                                parameterWithName("endTime").description("조회 기준 시간 (ISO-8601 포맷, 예: 2026-04-01T10:00:00)").optional()
                        ),
                        responseFields(
                                // ApiResponse 공통 필드 명세
                                fieldWithPath("success").description("성공 여부 (true/false)"),
                                fieldWithPath("message").description("응답 메시지 (성공 시 null 또는 안내 메시지)"),

                                // ChartResponseDto 필드 명세 (data 영역)
                                fieldWithPath("data.stockCode").description("종목 코드"),
                                fieldWithPath("data.timeframe").description("타임프레임"),
                                fieldWithPath("data.candles").description("캔들 리스트"),
                                fieldWithPath("data.candles[].timestamp").description("캔들 기준 시간"),
                                fieldWithPath("data.candles[].open").description("시가"),
                                fieldWithPath("data.candles[].high").description("고가"),
                                fieldWithPath("data.candles[].low").description("저가"),
                                fieldWithPath("data.candles[].close").description("종가"),
                                fieldWithPath("data.candles[].volume").description("거래량")
                        )
                ));
    }

    @Test
    @DisplayName("[실패] 필수 파라미터(timeframe) 누락 시 400 Bad Request")
    void givenTimeframeIsNull_whenGetCandles_thenResponse400Error() throws Exception {
        String stockCode = "005930";

        mockMvc.perform(get("/api/stocks/{stockCode}/charts/candles", stockCode)
                        .param("limit", "100"))
                .andDo(print())
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("[실패] 조회 개수(limit) 범위 미달 시 400 Bad Request")
    void given1LessThanLimit_whenGetCandles_thenResponse400Error() throws Exception {
        String stockCode = "005930";

        mockMvc.perform(get("/api/stocks/{stockCode}/charts/candles", stockCode)
                        .param("timeframe", "1d")
                        .param("limit", "0")) //
                .andDo(print())
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data").isEmpty());
    }
}