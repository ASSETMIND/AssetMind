package com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import java.util.ArrayList;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * KIS 실시간 체결 데이터 (H0STCNT0)의 응답을
 * KisRealTimeData DTO로 파싱
 */
@Slf4j
@Component
public class KisRealTimeDataParser {

    private static final String FIRST_DELIMITER = "\\|";
    private static final String SECOND_DELIMITER = "\\^";
    private static final int FIELD_COUNT = 46;

    public List<KisRealTimeData> parse(String payload) {
        List<KisRealTimeData> resultList = new ArrayList<>();

        try {
            String[] parts = payload.split(FIRST_DELIMITER);
            if (parts.length < 3) return resultList;

            // 주식 데이터의 개수 파악 및 Raw 데이터(^구분자로 이어진 실제 데이터 예: 종목코드, 주가, 시가, 등등) 추출
            int dataCount;
            String rawData;
            if (parts[2].matches("\\d+")) {
                // payload내의 주식 데이터가 여러개일 때 -> 0|H0STCNT0|002|005930^...
                // 002처럼 데이터의 개수가 들어옴
                dataCount = Integer.parseInt(parts[2]);
                rawData = parts[3];
            } else {
                // payload내의 주식 데이터가 단건일 때 -> 0|H0STCNT0|005930^...
                // 데이터의 개수가 들어오지 않음
                dataCount = 1;
                rawData = parts[2];
            }

            if (rawData == null || rawData.isEmpty()) return resultList;

            // ^ 구분자로 연속된 주가 데이터 분리
            String[] details = rawData.split(SECOND_DELIMITER, -1); // 빈 값 무시 X

            for (int i = 0; i < dataCount; i++) {
                int offset = i * FIELD_COUNT;
                resultList.add(mapToDto(details, offset));
            }
        } catch (Exception e) {
            log.error("KIS 실시간 체결 데이터 파싱 중 오류 발생. Payload: {}, Error: {}", payload, e.getMessage());
        }

        return resultList;
    }

    private KisRealTimeData mapToDto(String[] details, int offset) {
        return KisRealTimeData.builder()
                .stockCode(details[offset + 0])
                .executionTime(details[offset + 1])
                .currentPrice(Long.parseLong(details[offset + 2]))
                .changeSign(details[offset + 3])
                .priceChange(Long.parseLong(details[offset + 4]))
                .changeRate(Double.parseDouble(details[offset + 5]))
                .openPrice(Long.parseLong(details[offset + 7]))
                .highPrice(Long.parseLong(details[offset + 8]))
                .lowPrice(Long.parseLong(details[offset + 9]))
                .executionVolume(Long.parseLong(details[offset + 12]))
                .cumulativeVolume(Long.parseLong(details[offset + 13]))
                .cumulativeAmount(Long.parseLong(details[offset + 14]))
                .volumePower(Double.parseDouble(details[offset + 18]))
                .marketStatus(details[offset + 34])
                .build();
    }
}
