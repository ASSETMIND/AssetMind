package com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.market_access.domain.OrderBook.Level;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * KIS 실시간 호가 데이터 (H0STASP0)의 응답을
 * OrderBook 순수 도메인 객체로 파싱
 */
@Slf4j
@Component
public class KisOrderBookParser {

    private static final String FIRST_DELIMITER = "\\|";
    private static final String SECOND_DELIMITER = "\\^";

    public List<OrderBook> parse(String payload) {
        List<OrderBook> resultList = new ArrayList<>();

        try {
            String[] parts = payload.split(FIRST_DELIMITER);
            if (parts.length < 3) return resultList;

            // 호가 데이터의 개수 파악 및 Raw 데이터 추출
            int dataCount;
            String rawData;

            if (parts[2].matches("\\d+")) {
                dataCount = Integer.parseInt(parts[2]);
                rawData = parts[3];
            } else {
                dataCount = 1;
                rawData = parts[2];
            }

            if (rawData == null || rawData.isEmpty()) return resultList;

            String[] details = rawData.split(SECOND_DELIMITER, -1);

            // 데이터 1건당 차지하는 필드 개수 계산
            // KIS 호가 데이터는 보통 1건당 54~55개의 필드를 가짐
            int fieldCountPerData = details.length / dataCount;

            for (int i = 0; i < dataCount; i++) {
                int offset = i * fieldCountPerData;
                resultList.add(mapToDomain(details, offset));
            }
        } catch (Exception e) {
            log.error("KIS 실시간 호가 데이터 파싱 중 오류 발생. Payload: {}, Error: {}", payload, e.getMessage());
        }

        return resultList;
    }

    private OrderBook mapToDomain(String[] details, int offset) {
        String stockCode = details[offset];          // [0] 종목코드
        String timeStr = details[offset + 1];        // [1] 영업시간 (HHmmss)

        Long totalAskSize = Long.valueOf(details[offset + 43]); // [43] 총 매도호가 잔량
        Long totalBidSize = Long.valueOf(details[offset + 44]); // [44] 총 매수호가 잔량

        List<Level> levels = new ArrayList<>(10);

        // 1호가 ~ 10호가 루프 파싱
        for (int i = 0; i < 10; i++) {
            int levelNum = i + 1;
            Float askPrice = Float.valueOf(details[offset + 3 + i]);  // [3~12] 매도호가
            Float bidPrice = Float.valueOf(details[offset + 13 + i]); // [13~22] 매수호가
            Float askSize = Float.valueOf(details[offset + 23 + i]);  // [23~32] 매도호가 잔량
            Float bidSize = Float.valueOf(details[offset + 33 + i]);  // [33~42] 매수호가 잔량

            levels.add(Level.builder()
                    .level(levelNum)
                    .askPrice(askPrice)
                    .askSize(askSize)
                    .bidPrice(bidPrice)
                    .bidSize(bidSize)
                    .build()
            );
        }

        return OrderBook.builder()
                .stockCode(stockCode)
                .marketTime(LocalTime.parse(timeStr))
                .totalAskSize(totalAskSize)
                .totalBidSize(totalBidSize)
                .build();
    }
}
