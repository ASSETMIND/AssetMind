package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import java.util.List;

/**
 * 실시간 체결 데이터에서 1분봉(OHLCV_1m), 1일봉(OHLCV_1d) 데이터를 인메모리에 캐싱하고 집계하기 위한 도메인 레포지토리 인터페이스
 */
public interface CandleRepository {

    /**
     * 실시간 틱 데이터가 들어올 때마다 타입에 따라 해당 분(Minute) 또는 일(Day)의 봉들을 갱신
     */
    void save(RealTimeStockTradeEvent event, CandleType type);

    /**
     * 타겟 시간(예: "202603240910" 또는 "20260324")에 완성된
     * 모든 종목의 캔들 데이터를 읽어오고 캐시에서 삭제한다.
     *
     * @param targetTime 타겟 분 (yyyyMMddHHmm)
     * @return 완성된 OHLCV DTO 배열
     */
    List<OhlcvDto> flushCandlesByMinutes(String targetTime, CandleType type);

}
