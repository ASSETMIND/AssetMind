package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1dRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1dJpaEntity;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * {@link Ohlcv1dRepository} 인터페이스를 JPA 기술로 구현한 어탭터 구현체
 *
 * 도메인 계층에서 전달받은 순수 DTO {@link OhlcvDto}를
 * 영속성 객체 {@link com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1dJpaEntity}로 변환하여 DB에 저장
 *
 */
@Repository
@RequiredArgsConstructor
public class Ohlcv1dJpaAdapter implements Ohlcv1dRepository {

    private final Ohlcv1dJpaRepository ohlcv1dJpaRepository;

    @Override
    public void saveAll(List<OhlcvDto> dtoList) {
        List<Ohlcv1dJpaEntity> entities = dtoList.stream()
                .map(this::toEntity)
                .toList();

        ohlcv1dJpaRepository.saveAll(entities);
    }

    @Override
    public void save(OhlcvDto ohlcvDto) {
        ohlcv1dJpaRepository.save(toEntity(ohlcvDto));
    }

    @Override
    public Optional<OhlcvDto> findCandleByDay(String stockCode, LocalDate date) {
        // (00:00:00 ~ 다음날 00:00:00)로 변환
        LocalDateTime startOfDay = date.atStartOfDay();
        LocalDateTime endOfDay = date.plusDays(1).atStartOfDay();

        return ohlcv1dJpaRepository.findCandleByDay(stockCode, startOfDay, endOfDay)
                .map(this::toDto);
    }

    private Ohlcv1dJpaEntity toEntity(OhlcvDto dto) {
        return Ohlcv1dJpaEntity.builder()
                .stockCode(dto.stockCode())
                .candleTimestamp(dto.candleTimestamp())
                .openPrice(dto.openPrice())
                .highPrice(dto.highPrice())
                .lowPrice(dto.lowPrice())
                .closePrice(dto.closePrice())
                .volume(dto.volume())
                .build();
    }

    private OhlcvDto toDto(Ohlcv1dJpaEntity entity) {
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
