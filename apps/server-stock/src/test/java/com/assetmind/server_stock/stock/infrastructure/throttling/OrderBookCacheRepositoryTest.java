package com.assetmind.server_stock.stock.infrastructure.throttling;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import java.time.LocalTime;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class OrderBookCacheRepositoryTest {

    private OrderBookCacheRepository cacheRepository;

    @BeforeEach
    void setUp() {
        cacheRepository = new OrderBookCacheRepository();
    }

    @Test
    @DisplayName("새로운 호가 데이터가 저장되면 flag가 true가 되고, 조회 시 false로 변경된다.")
    void givenNewOrderBook_whenSave_thenReturnDataAndFlagTrueToFalse() {
        // given
        String stockCode = "005930";
        OrderBook orderBook = createDummyOrderBook(stockCode);

        // when
        cacheRepository.save(orderBook);

        // then
        OrderBook snapshot = cacheRepository.getIfDirtyAndClean(stockCode);
        assertThat(snapshot).isNotNull();
        assertThat(snapshot.stockCode()).isEqualTo(stockCode);

        // 직후에 다시 꺼내면 isDirty가 false로 변경되었으므로 null이 반환
        OrderBook cleanOrderBook = cacheRepository.getIfDirtyAndClean(stockCode);
        assertThat(cleanOrderBook).isNull();
    }

    @Test
    @DisplayName("100개의 스레드가 동시에 같은 종목을 덮어써도 예외가 발생하지 않고 최종 상태 flag가 true로 유지된다.")
    void given100Thread_whenSave_thenNotOccurErrorAndFlagIsTrue() throws InterruptedException {
        // given
        String stockCode = "005930";
        int threadCount = 100;
        ExecutorService executorService = Executors.newFixedThreadPool(32);
        CountDownLatch latch = new CountDownLatch(threadCount);

        // when
        for (int i = 0; i < threadCount; i++) {
            executorService.submit(() -> {
                try {
                    OrderBook dummyOrderBook = createDummyOrderBook(stockCode);
                    cacheRepository.save(dummyOrderBook);
                } finally {
                    latch.countDown();
                }
            });
        }
        latch.await();

        // then
        // 100개의 스레드가 동시에 덮어쓰기 하더라도 맵에 1개의 종목이 정상적으로 존재
        assertThat(cacheRepository.getAllStockCodes()).hasSize(1);

        // 최종 flag 상태는 스레드가 덮어썻으므로 반드시 true 상태여야함
        OrderBook result = cacheRepository.getIfDirtyAndClean(stockCode);
        assertThat(result).isNotNull();
    }

    private OrderBook createDummyOrderBook(String stockCode) {
        return OrderBook.builder().
                stockCode(stockCode)
                .marketTime(LocalTime.now())
                .totalBidSize(100L)
                .totalAskSize(100L)
                .levels(List.of())
                .build();
    }
}
