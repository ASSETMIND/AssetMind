package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * 실시간 체결 데이터의 1일봉 캔들 데이터를 저장하고 조회하기 위한 도메인 레포지토리 인터페이스
 */
public interface Ohlcv1dRepository {

    /**
     * 1일봉 여러종목 캔들 데이터들을 한번에 저장
     * @param dtoList 1일봉 데이터가 담긴 여러 종목의 OhlcvDto
     */
    void saveAll(List<OhlcvDto> dtoList);

    /**
     * 완성된 1일봉 캔들 데이터를 저장
     * @param ohlcvDto 1일봉 데이터가 담긴 Ohclv DTO
     */
    void save(OhlcvDto ohlcvDto);

    /**
     * DB에 저장되어있는 1일봉 캔들 데이터를 조회한다.
     * 3일봉, 5일봉, 주봉, 월봉, 년봉 등등 롤업 계산에도 사용
     * @param stockCode 종목 코드
     * @param date 조회 날짜
     */
    Optional<OhlcvDto> findCandleByDay(String stockCode, LocalDate date);
}
