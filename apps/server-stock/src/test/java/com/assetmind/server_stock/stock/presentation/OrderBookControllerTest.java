package com.assetmind.server_stock.stock.presentation;

import static org.mockito.BDDMockito.*;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.mockmvc.RestDocumentationRequestBuilders.get;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.*;
import static org.springframework.restdocs.payload.PayloadDocumentation.*;
import static org.springframework.restdocs.request.RequestDocumentation.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.stock.application.OrderBookService;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import com.assetmind.server_stock.stock.presentation.dto.OrderBookResponseDto;
import java.time.LocalTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.restdocs.AutoConfigureRestDocs;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.restdocs.payload.JsonFieldType;
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
        OrderBookResponseDto dummyOrderBook = OrderBookResponseDto.builder()
                .stockCode(stockCode)
                .marketTime(String.valueOf(LocalTime.of(15, 30, 0)))
                .totalBidSize("1500")
                .totalAskSize("2000")
                .levels(List.of())
                .build();

        given(orderBookService.getOrderBookSnapshot(stockCode)).willReturn(dummyOrderBook);

        // when & then
        mockMvc.perform(get("/api/stocks/{stockCode}/orderbook", stockCode))
                .andDo(print())
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.stockCode").value(stockCode))
                .andExpect(jsonPath("$.data.totalBidSize").value("1500"))

                // 문서화 로직 추가
                .andDo(document("orderbook/get-snapshot-success",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        pathParameters(
                                parameterWithName("stockCode").description("조회할 주식 종목 코드 (6자리 숫자)")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("API 호출 성공 여부").optional(),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("응답 메시지 (성공 시 null)").optional(),

                                fieldWithPath("data").type(JsonFieldType.OBJECT).description("호가 스냅샷 데이터"),
                                fieldWithPath("data.stockCode").type(JsonFieldType.STRING).description("종목 코드"),
                                fieldWithPath("data.marketTime").type(JsonFieldType.STRING).description("호가 수신 시간 (HHmmss 등)"),

                                fieldWithPath("data.totalAskSize").type(JsonFieldType.STRING).description("총 매도 호가 잔량"),
                                fieldWithPath("data.totalBidSize").type(JsonFieldType.STRING).description("총 매수 호가 잔량"),

                                fieldWithPath("data.levels[]").type(JsonFieldType.ARRAY).description("1~10단계 호가 리스트").optional(),
                                fieldWithPath("data.levels[].level").type(JsonFieldType.NUMBER).description("호가 단계 (1~10)").optional(),
                                fieldWithPath("data.levels[].askPrice").type(JsonFieldType.STRING).description("매도 호가").optional(),
                                fieldWithPath("data.levels[].askSize").type(JsonFieldType.STRING).description("매도 잔량").optional(),
                                fieldWithPath("data.levels[].bidPrice").type(JsonFieldType.STRING).description("매수 호가").optional(),
                                fieldWithPath("data.levels[].bidSize").type(JsonFieldType.STRING).description("매수 잔량").optional()
                        )
                ));

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
                .andExpect(jsonPath("$.data").isEmpty())

                .andDo(document("orderbook/get-snapshot-success-empty",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        pathParameters(
                                parameterWithName("stockCode").description("조회할 주식 종목 코드 (6자리 숫자)")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("API 호출 성공 여부").optional(),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("응답 메시지 (데이터 없음 알림)"),
                                fieldWithPath("data").type(JsonFieldType.NULL).description("데이터 (캐시가 비어있을 경우 null)")
                        )
                ));
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
                .andExpect(jsonPath("$.message").value(ErrorCode.INVALID_STOCK_PARAMETER.getMessage()))

                // 문서화 로직 추가
                .andDo(document("orderbook/get-snapshot-fail-invalid-code",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        pathParameters(
                                parameterWithName("stockCode").description("조회할 주식 종목 코드 (잘못된 요청)")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("API 호출 실패 (false)").optional(),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("에러 상세 메시지"),
                                fieldWithPath("data").type(JsonFieldType.NULL).description("데이터 (null)").optional()
                        )
                ));
    }
}
