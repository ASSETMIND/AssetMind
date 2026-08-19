package com.assetmind.server_stock.market_access.infrastructure.scheduler;

import static org.mockito.BDDMockito.*;
import static org.mockito.Mockito.inOrder;

import com.assetmind.server_stock.market_access.application.port.RealTimeStockDataPort;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class DailyMarketLifecycleSchedulerTest {

    @Mock
    private RealTimeStockDataPort realTimeStockDataPort;

    @Mock
    private StockMetadataProvider stockMetadataProvider;

    @InjectMocks
    private DailyMarketLifecycleScheduler scheduler;

    @Test
    @DisplayName("성공: 장 시작 시 연결 준비, 종목 조회, 구독 요청이 순서대로 실행되어야 한다.")
    void givenStockCodes_whenWakeUpPipeline_thenSuccessSequence() {
        // given
        List<String> mockStockCodes = List.of("005930", "000660", "035420");
        given(stockMetadataProvider.getAllStockCodes()).willReturn(mockStockCodes);

        // when
        scheduler.wakeUpPipeline();

        // then
        // 호출 순서 검증을 위한 InOrder 객체 생성
        InOrder inOrder = inOrder(realTimeStockDataPort, stockMetadataProvider);

        // 1. 연결 준비 -> 2. 종목 조회 -> 3. 구독 순서 확인
        inOrder.verify(realTimeStockDataPort).prepareConnection();
        inOrder.verify(stockMetadataProvider).getAllStockCodes();
        inOrder.verify(realTimeStockDataPort).subscribe(mockStockCodes);
    }

    @Test
    @DisplayName("실패방어: 연결 준비 중 에러가 발생해도 예외를 내부에서 처리하고 중단되지 않는다.")
    void givenFailCase_whenWakeUpPipeline_thenHandleException() {
        // given
        willThrow(new RuntimeException("KIS Connection Timeout"))
                .given(realTimeStockDataPort).prepareConnection();

        // when & then
        // 예외가 외부로 던져지지 않아야 스케줄러 스레드가 유지됨
        org.junit.jupiter.api.Assertions.assertDoesNotThrow(() -> {
            scheduler.wakeUpPipeline();
        });

        // prepareConnection 이후의 로직은 실행되지 않았는지 확인
        verify(stockMetadataProvider, never()).getAllStockCodes();
        verify(realTimeStockDataPort, never()).subscribe(any());
    }

    @Test
    @DisplayName("성공: 장 마감 시 disconnect가 정상적으로 호출되어야 한다.")
    void whenSleepPipeline_thenSuccess() {
        // when
        scheduler.sleepPipeline();

        // then
        verify(realTimeStockDataPort, times(1)).disconnect();
    }

    @Test
    @DisplayName("실패방어: 종료 중 에러가 발생해도 예외를 내부에서 처리한다.")
    void givenFailCase_whenSleepPipeline_thenHandleException() {
        // given
        willThrow(new RuntimeException("Disconnect Error"))
                .given(realTimeStockDataPort).disconnect();

        // when & then
        org.junit.jupiter.api.Assertions.assertDoesNotThrow(() -> {
            scheduler.sleepPipeline();
        });
    }
}