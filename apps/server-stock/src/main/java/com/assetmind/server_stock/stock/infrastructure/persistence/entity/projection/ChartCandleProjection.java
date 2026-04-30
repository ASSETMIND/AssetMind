package com.assetmind.server_stock.stock.infrastructure.persistence.entity.projection;

import java.time.LocalDateTime;

/**
 * JPA Native 동적 쿼리에 대한 집계 결과 값을 객체로 받기 위한 인터페이스
 *
 * Spring Data Jpa가 해당 인터페이스를 동적 프록시 방법으로 내부적으로 가짜 객체를 생성해낸다.
 */
public interface ChartCandleProjection {
    LocalDateTime getCandleTimestamp();
    Double getOpen();
    Double getHigh();
    Double getLow();
    Double getClose();
    Long getVolume();

}
