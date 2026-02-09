package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import java.util.List;

/**
 * 실시간 주가 데이터 스냅샷과 실시간 랭킹 정보를 다루는 행동을 정의
 *
 * 해당 인터페이스는 Domain 계층인데도 불구하고 편의성을 위해 Infrastructure 계층의 {@link StockPriceRedisEntity}를 의존
 * 1. 실시간 주가 데이터는 상태 변경이 없는 객체이므로 복잡한 도메인 로직이 필요없음.
 * 2. 실시간 주가 데이터는 초당 수백 건 이상의 저장(쓰기)가 발생함, 이를 도메인 모델로 매핑하는 비용을 줄이기 위해 엔티티를 의존
 *
 * 이 2가지 이유로 헥사고널 아키텍처를 정확하게 지키기 위해서 도메인 모델 객체를 만들기보다는
 * 의도적으로 위반하는 방향이 더 옳다고 판단했음
 */
public interface StockSnapshotRepository {

    // 실시간 스냅샷 저장
    void save(StockPriceRedisEntity entity);

    // 거래 대금 상위 N개 종목 조회
    List<StockPriceRedisEntity> getTopStocksByTradeValue(int limit);

    // 거래량 상위 N개 종목 조회
    List<StockPriceRedisEntity> getTopStocksByTradeVolume(int limit);
}
