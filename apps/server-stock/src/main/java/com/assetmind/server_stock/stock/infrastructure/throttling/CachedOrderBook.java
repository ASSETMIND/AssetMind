package com.assetmind.server_stock.stock.infrastructure.throttling;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import java.util.concurrent.atomic.AtomicBoolean;
import lombok.Getter;

/**
 * L1(Lever1, 인메모리 캐시) 캐시 내부에 저장될 객체
 * 멀티스레드 환경에서 안전한 상태 관리를 보장
 */
public class CachedOrderBook {
    @Getter
    private OrderBook orderBook;

    // 멀티스레드 환경에서 OrderBook 상태의 원자성을 지키기 위해 CAS 사용하는 AtomicBoolean 이용
    private final AtomicBoolean isDirty = new AtomicBoolean(false);

    public CachedOrderBook(OrderBook initOrderBook) {
        this.orderBook = initOrderBook;
        this.isDirty.set(true);
    }

    /**
     * KIS에서 새로운 호가 데이터가 유입될 때마다 덮어씀
     */
    public void update(OrderBook newOrderBook) {
        this.orderBook = newOrderBook;
        this.isDirty.set(true);
    }

    /**
     * 현재 데이터의 상태를 확인하기 위함
     */
    public boolean isDirty() {
        return this.isDirty.get();
    }

    /**
     * 스케줄러가 데이터를 발송하기 위해 데이터를 꺼낼 때 사용
     * true 였다면 false 변경하고 true를 반환 (true로 변경하는건 아님 반환만 true)
     */
    public OrderBook getOrderBookAndClean() {
        // 읽기와 쓰기(false로 변경)를 하드웨어 레벨에서 CAS(Compare And Swap) 방식으로 하나의 단계로 처리를 하여
        // 멀티스레드 환경에서 경쟁 상태를 초기에 방지함
        if(isDirty.compareAndSet(true, false)) {
            return this.orderBook;
        }

        return null;
    }

}
