package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.TickId;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * 실제 PostgreSQL의 raw_tick 테이블과 통신하여 DB I/O를 수행하는 JPA 레포지토리
 * DB 단에서는 일별 Range Partitioning이 적용되어 있지만
 * 애플리케이션 단에서는 부모 테이블(raw_tick)을 향해 쿼리를 날리면 PostgreSQL 내부 라우팅을 통해 알맞는 파이션에서 데이터를 저장 및 조회한다.
 */
public interface RawTickJpaRepository extends JpaRepository<RawTickJpaEntity, TickId> {

    /**
     * 특정 종목 코드를 기준으로 체결 시간(trade_timestamp) 내림차순 정렬하여 데이터를 조회
     */
    @Query("SELECT r FROM RawTickJpaEntity  r WHERE  r.stockCode = :stockCode ORDER BY r.tradeTimestamp DESC")
    List<RawTickJpaEntity> findRecentTicks(@Param("stockCode") String stockCode, Pageable pageable);
}
