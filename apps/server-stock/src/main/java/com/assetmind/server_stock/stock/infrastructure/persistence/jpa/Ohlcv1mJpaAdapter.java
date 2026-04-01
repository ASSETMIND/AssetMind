package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1dJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1mJpaEntity;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * {@link Ohlcv1mRepository} 인터페이스를 JPA 기술로 구현한 어탭터 구현체
 *
 * 도메인 계층에서 전달받은 순수 DTO {@link OhlcvDto}를
 * 영속성 객체 {@link com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1mJpaEntity}로 변환하여 DB에 저장
 *
 * 현재는 JPA의 saveAll()을 사용하고 있으나 향후 성능 최적화가 필요할 시에는 JdbcTemplate으로 변경할 예정
 */
@Repository
@RequiredArgsConstructor
public class Ohlcv1mJpaAdapter implements Ohlcv1mRepository {

    private final Ohlcv1mJpaRepository ohlcv1mJpaRepository;

    @Override
    public void saveAll(List<OhlcvDto> dtoList) {
        List<Ohlcv1mJpaEntity> entities = dtoList.stream()
                .map(dto -> Ohlcv1mJpaEntity.builder()
                        .stockCode(dto.stockCode())
                        .candleTimestamp(dto.candleTimestamp())
                        .openPrice(dto.openPrice())
                        .highPrice(dto.highPrice())
                        .lowPrice(dto.lowPrice())
                        .closePrice(dto.closePrice())
                        .volume(dto.volume())
                        .build()
                ).toList();

        // 리스트 내부에 식별자가 같은 데이터가 있다면 최산 값으로 덮어씀
        Map<String, Ohlcv1mJpaEntity> deduplicatedMap = entities.stream()
                .collect(Collectors.toMap(
                        entity -> entity.getStockCode() + "_" + entity.getCandleTimestamp()
                                .toString(),
                        entity -> entity,
                        (existing, replacement) -> replacement
                ));

        Collection<Ohlcv1mJpaEntity> uniqueEntities = deduplicatedMap.values();

        ohlcv1mJpaRepository.saveAll(uniqueEntities);
    }

    @Override
    public List<OhlcvDto> findCandlesByDate(String stockCode, LocalDate date) {
        LocalDateTime startOfDay = date.atStartOfDay();
        LocalDateTime endOfDay = date.plusDays(1).atStartOfDay();

        List<Ohlcv1mJpaEntity> entities = ohlcv1mJpaRepository.findCandlesByTimeRange(
                stockCode, startOfDay, endOfDay);

        return entities.stream()
                .map(this::toDto)
                .toList();
    }

    private OhlcvDto toDto(Ohlcv1mJpaEntity entity) {
        return new OhlcvDto(
                entity.getStockCode(),
                entity.getCandleTimestamp(),
                entity.getOpenPrice(),
                entity.getHighPrice(),
                entity.getLowPrice(),
                entity.getClosePrice(),
                entity.getVolume()
        );
    }
}
