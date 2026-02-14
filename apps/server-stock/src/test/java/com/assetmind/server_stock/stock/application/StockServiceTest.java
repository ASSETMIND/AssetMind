package com.assetmind.server_stock.stock.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.application.mapper.StockMapper;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.domain.repository.StockHistoryRepository;
import com.assetmind.server_stock.stock.domain.repository.StockSnapshotRepository;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class StockServiceTest {

    @Mock
    private StockSnapshotRepository stockSnapshotRepository;

    @Mock
    private StockHistoryRepository stockHistoryRepository;

    @Mock
    private StockMetadataProvider stockMetadataProvider;

    @Mock
    private StockMapper stockMapper;

    @InjectMocks
    private StockService stockService;

    // 테스트용 더미 데이터 생성 헬퍼 메서드
    private RealTimeStockTradeEvent createEvent(String stockCode) {
        return new RealTimeStockTradeEvent(
                stockCode,
                "100000",
                80000L,
                79000L,
                81000L,
                78000L,
                1000L,
                "2",
                1.5,
                10L,
                10000000L,
                200000L,
                LocalDateTime.now()
        );
    }

    @Nested
    @DisplayName("실시간 주가 처리 (processRealTimeTrade)")
    class ProcessRealTimeTradeTest {

        @Test
        @DisplayName("성공: 정상적인 이벤트가 들어오면 Redis와 DB에 저장되어야 한다")
        void givenEvent_whenProcessRealTImeTrade_thenSavedRepository() {
            // given
            String stockCode = "005930";
            String stockName = "삼성전자";
            RealTimeStockTradeEvent event = createEvent(stockCode);

            // Mocking 동작 정의
            given(stockMetadataProvider.getStockName(stockCode)).willReturn(stockName);
            given(stockMapper.toRedisEntity(eq(event), eq(stockName))).willReturn(
                    StockPriceRedisEntity.builder().build());
            given(stockMapper.toJpaEntity(eq(event))).willReturn(StockDataEntity.builder().build());

            // when
            stockService.processRealTimeTrade(event);

            // then
            // 메타데이터 조회 호출 확인
            verify(stockMetadataProvider).getStockName(stockCode);
            // Redis 저장소 호출 확인
            verify(stockSnapshotRepository, times(1)).save(any(StockPriceRedisEntity.class));
            // DB 저장소 호출 확인
            verify(stockHistoryRepository, times(1)).save(any(StockDataEntity.class));
        }

        @Test
        @DisplayName("실패: 이벤트 객체가 null이면 예외가 발생해야 한다")
        void givenNullEvent_whenProcessRealTimeTrade_thenThrowException() {
            // when & then
            assertThatThrownBy(() -> stockService.processRealTimeTrade(null))
                    .isInstanceOf(InvalidStockParameterException.class)
                    .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_STOCK_PARAMETER);
        }

        @Test
        @DisplayName("실패: 종목 코드(stockCode)가 null이면 예외가 발생해야 한다")
        void givenNullStockCode_whenProcessRealTimeTrade_thenThrowException() {
            // given
            RealTimeStockTradeEvent event = createEvent(null);

            // when & then
            assertThatThrownBy(() -> stockService.processRealTimeTrade(event))
                    .isInstanceOf(InvalidStockParameterException.class);
        }

        @Test
        @DisplayName("실패: 종목 코드(stockCode)가 빈 문자열이면 예외가 발생해야 한다")
        void givenEmptyStockCode_whenProcessRealTimeTrade_thenThrowException() {
            // given
            RealTimeStockTradeEvent event = createEvent("");

            // when & then
            assertThatThrownBy(() -> stockService.processRealTimeTrade(event))
                    .isInstanceOf(InvalidStockParameterException.class);
        }
    }

    @Nested
    @DisplayName("랭킹 조회 (Ranking)")
    class RankingTest {

        @Test
        @DisplayName("성공: 거래대금 순 랭킹 조회 시 Redis Repository를 호출해서 올바른 RedisEntity를 리턴해야한다.")
        void givenLimit_whenGetTopStocksByTradeValue_ThenReturnRedisEntity() {
            // given
            int limit = 10;
            List<StockPriceRedisEntity> expectedList = List.of(StockPriceRedisEntity.builder().build());
            given(stockSnapshotRepository.getTopStocksByTradeValue(limit)).willReturn(expectedList);

            // when
            List<StockPriceRedisEntity> result = stockService.getTopStocksByTradeValue(limit);

            // then
            assertThat(result).isEqualTo(expectedList);
            verify(stockSnapshotRepository).getTopStocksByTradeValue(limit);
        }

        @Test
        @DisplayName("성공: 거래량 순 랭킹 조회 시 Repository를 호출해서 올바른 RedisEntity를 리턴해야한다.")
        void givenLimit_whenGetTopStocksByTradeVolume_ThenReturnRedisEntity() {
            // given
            int limit = 5;
            List<StockPriceRedisEntity> expectedList = List.of(StockPriceRedisEntity.builder().build());
            given(stockSnapshotRepository.getTopStocksByTradeVolume(limit)).willReturn(expectedList);

            // when
            List<StockPriceRedisEntity> result = stockService.getTopStocksByTradeVolume(limit);

            // then
            assertThat(result).isEqualTo(expectedList);
            verify(stockSnapshotRepository).getTopStocksByTradeVolume(limit);
        }
    }

    @Nested
    @DisplayName("시계열 데이터 조회 (History)")
    class HistoryTest {

        @Test
        @DisplayName("성공: 유효한 종목 코드와 limit으로 조회 시 Repository를 호출해서 올바른 JpaEntity를 리턴해야한다.")
        void givenStockCodeAndLimit_whenGetStockRecentHistory_thenReturnJpaEntity() {
            // given
            String stockCode = "005930";
            int limit = 20;
            List<StockDataEntity> expectedHistory = List.of(StockDataEntity.builder().build());

            given(stockHistoryRepository.findRecentData(stockCode, limit)).willReturn(expectedHistory);

            // when
            List<StockDataEntity> result = stockService.getStockRecentHistory(stockCode, limit);

            // then
            assertThat(result).isEqualTo(expectedHistory);
            verify(stockHistoryRepository).findRecentData(stockCode, limit);
        }

        @Test
        @DisplayName("실패: 종목 코드가 null이면 예외가 발생해야 한다")
        void givenNullStockCode_whenGetStockRecentHistory_thenThrowException() {
            // when & then
            assertThatThrownBy(() -> stockService.getStockRecentHistory(null, 10))
                    .isInstanceOf(InvalidStockParameterException.class)
                    .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_STOCK_PARAMETER);
        }

        @Test
        @DisplayName("실패: 종목 코드가 빈 문자열이면 예외가 발생해야 한다")
        void givenEmptyStockCode_whenGetStockRecentHistory_thenThrowException() {
            // when & then
            assertThatThrownBy(() -> stockService.getStockRecentHistory("  ", 10))
                    .isInstanceOf(InvalidStockParameterException.class);
        }
    }
}