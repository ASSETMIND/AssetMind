package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import java.time.LocalDate;
import java.time.LocalDateTime;
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
     * DB에 저장되어있는 1일봉 캔들(한개) 데이터를 조회한다.
     * 3일봉, 5일봉, 주봉, 월봉, 년봉 등등 롤업 계산에도 사용
     * @param stockCode 종목 코드
     * @param date 조회 날짜
     */
    Optional<OhlcvDto> findCandleByDay(String stockCode, LocalDate date);

    /**
     * DB에 저장되어있는 2000년 01월 01일 부터 EndTime 까지의 N일봉 데이터를 조회한다.
     * @param stockCode 종목 코드
     * @param intervalString 날짜의 간격(예: 3일봉 - 3 days, 1주봉 - 7 days)
     * @param endTime N일봉을 조회하려는 기간의 마지막 날짜
     * @param limit 조회하려는 데이터의 개수
     * @return 캔들 데이터 DTO 리스트
     */
    List<OhlcvDto> findDynamicDailyCandles(String stockCode, String intervalString, LocalDateTime endTime, int limit);

    /**
     * DB에 저장되어있는 2000년 01월 01일 부터 현재까지의 N월봉 데이터를 조회한다.
     * @param stockCode 종목 코드
     * @param endTime N월봉을 조회하려는 기간의 마지막 날짜
     * @param limit 조회하려는 데이터의 개수
     * @return 캔들 데이터 DTO 리스트
     */
    List<OhlcvDto> findMonthlyCandles(String stockCode, LocalDateTime endTime, int limit);

    /**
     * DB에 저장되어있는 2000년 01월 01일 부터 현재까지의 N년봉 데이터를 조회한다.
     * @param stockCode 종목 코드
     * @param endTime N년봉을 조회하려는 기간의 마지막 날짜
     * @param limit 조회하려는 데이터의 개수
     * @return 캔들 데이터 DTO 리스트
     */
    List<OhlcvDto> findYearlyCandles(String stockCode, LocalDateTime endTime, int limit);
}
