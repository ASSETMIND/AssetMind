package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import java.util.List;

/**
 * 과거 차트 데이터를 저장하고 조회하는 행동을 정의
 *
 * 해당 인터페이스는 Domain 계층인데도 불구하고 편의성을 위해 Infrastructure 계층의 {@link StockDataEntity}를 의존
 * 1. 과거 차트 데이터는 상태 변경이 없는 객체이므로 복잡한 도메인 로직이 필요없음.
 * 2. 과거 차트 데이터를 조회시 수천 건의 데이터 조회가 필요함 이를 도메인 모델로 매핑하는 비용을 줄이기 위해 엔티티를 직접 반환
 *
 * 이 2가지 이유로 헥사고널 아키텍처를 정확하게 지키기 위해서 도메인 모델 객체를 만들기보다는
 * 의도적으로 위반하는 방향이 더 옳다고 판단했음
 */
public interface StockHistoryRepository {

    // 체결 데이터 저장
    StockDataEntity save(StockDataEntity dataEntity);

    // 특정 종목에 대한 저장된 데이터 조회
    List<StockDataEntity> findRecentData(String stockCode, int limit);
}
