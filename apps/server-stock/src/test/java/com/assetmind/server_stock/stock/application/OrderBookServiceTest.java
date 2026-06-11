package com.assetmind.server_stock.stock.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.exception.InvalidOrderBookParameterException;
import com.assetmind.server_stock.stock.infrastructure.throttling.OrderBookCacheRepository;
import com.assetmind.server_stock.stock.presentation.dto.OrderBookResponseDto;
import java.time.LocalTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class OrderBookServiceTest {

    @InjectMocks
    private OrderBookService orderBookService;

    @Mock
    private OrderBookCacheRepository cacheRepository;

    @Mock
    private StockMetadataProvider stockMetadataProvider;

    @Test
    @DisplayName("지원하는 종목 코드로 조회 시, 캐시에 데이터가 있으면 호가 스냅샷을 반환한다.")
    void givenSupportedStockCode_whenGetSnapshot_thenReturnOrderBook() {
        // given
        String validStockCode = "005930";
        OrderBook dummyOrderBook = OrderBook.builder()
                .stockCode(validStockCode)
                .marketTime(LocalTime.now())
                .totalBidSize(100L)
                .totalAskSize(200L)
                .levels(List.of())
                .build();

        given(stockMetadataProvider.isExist(validStockCode)).willReturn(true);
        given(cacheRepository.getSnapshot(validStockCode)).willReturn(dummyOrderBook);

        // when
        OrderBookResponseDto result = orderBookService.getOrderBookSnapshot(validStockCode);

        // then
        assertThat(result).isNotNull();
        assertThat(result.stockCode()).isEqualTo(validStockCode);

        // 의존성 호출 검증
        verify(stockMetadataProvider).isExist(validStockCode);
        verify(cacheRepository).getSnapshot(validStockCode);
    }

    @Test
    @DisplayName("지원하는 종목 코드이지만 캐시가 비어있을 경우, null을 반환한다.")
    void givenSupportedStockCode_whenCacheIsEmpty_thenReturnNull() {
        // given
        String validStockCode = "005930";

        given(stockMetadataProvider.isExist(validStockCode)).willReturn(true);
        given(cacheRepository.getSnapshot(validStockCode)).willReturn(null);

        // when
        OrderBookResponseDto result = orderBookService.getOrderBookSnapshot(validStockCode);

        // then
        assertThat(result).isNull();
        verify(stockMetadataProvider).isExist(validStockCode);
        verify(cacheRepository).getSnapshot(validStockCode);
    }

    @Test
    @DisplayName("지원하지 않는 종목 코드로 조회 시, InvalidOrderBookParameterException 예외가 발생한다.")
    void givenUnsupportedStockCode_whenGetSnapshot_thenThrowException() {
        // given
        String invalidStockCode = "999999";

        // 메타데이터 프로바이더가 false를 반환하도록 설정
        given(stockMetadataProvider.isExist(invalidStockCode)).willReturn(false);

        // when & then
        assertThatThrownBy(() -> orderBookService.getOrderBookSnapshot(invalidStockCode))
                .isInstanceOf(InvalidOrderBookParameterException.class)
                // 예외 내부에 정의된 ErrorCode가 맞는지 검증
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.UNSUPPORTED_ORDER_BOOK);

        // 검증: 예외가 터졌으므로 캐시 저장소는 절대 호출되지 않아야 함
        verify(cacheRepository, never()).getSnapshot(invalidStockCode);
    }
}