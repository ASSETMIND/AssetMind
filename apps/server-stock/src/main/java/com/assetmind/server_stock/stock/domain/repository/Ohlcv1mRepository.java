package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import java.time.LocalDate;
import java.util.List;

/**
 * 실시간 체결 데이터의 1분봉 캔들 데이터를 저장하고 조회하기 위한 도메인 레포지토리 인터페이스
 */
public interface Ohlcv1mRepository {

    /**
     * 완성된 1분봉 캔들 리스트를 데이터베이스에 일괄 저장
     * @param dtoList Redis 등에서 수집된 1분봉 OHLCV DTO 리스트
     */
    void saveAll(List<OhlcvDto> dtoList);

    /**
     * 1일봉 롤업 계산을 위해, 특정 종목의 특정 날짜에 해당하는 모든 1분동 데이터를 조회
     * @param stockCode 종목 코드
     * @param date 조회한 날짜
     * @return 해당 날짜의 1분봉 OHLCV DTO 리스트
     */
    List<OhlcvDto> findCandlesByDate(String stockCode, LocalDate date);
}
