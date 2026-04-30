package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.domain.repository.RawTickRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Repository;

/**
 * 도메인 계층의 {@link RawTickRepository} 인터페이스를 Spring Data JPA 기술을 사용하여 구현한 구현체이다.
 * DIP를 통해 도메인 로직이 인프라 기술 변경에 영향을 받지 않도록 격리한다.
 *
 * 추후 실시간으로 저장되는 데이터가 병목으로 인해 문제가 발생한다면 JPA 대신 JdbcTemplate로 변경할 예정이다.
 */
@Repository
@RequiredArgsConstructor
public class RawTickJpaAdapter implements RawTickRepository {

    private final RawTickJpaRepository rawTickJpaRepository;

    @Override
    public RawTickJpaEntity save(RawTickJpaEntity rawTickJpaEntity) {
        return rawTickJpaRepository.save(rawTickJpaEntity);
    }

    @Override
    public List<RawTickJpaEntity> findRecentData(String stockCode, int limit) {
        Pageable page = PageRequest.of(0, limit);
        return rawTickJpaRepository.findRecentTicks(stockCode, page);
    }
}
