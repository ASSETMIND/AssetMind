package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import org.springframework.data.repository.CrudRepository;

/**
 * 주식 실시간 스냅샷(StockPriceRedisEntity) 관리를 위한 Redis CRUD 리포지토리
 *
 * Spring Data Redis의 Repository 기능을 사용
 * {@link StockPriceRedisEntity} 객체를 Redis의 Hash 자료구조로 변환하여 저장하고 조회
 */
public interface StockPriceRedisRepository extends CrudRepository<StockPriceRedisEntity, String> {

}
