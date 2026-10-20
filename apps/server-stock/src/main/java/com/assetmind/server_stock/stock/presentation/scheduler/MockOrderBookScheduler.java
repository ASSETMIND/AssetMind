package com.assetmind.server_stock.stock.presentation.scheduler;

import com.assetmind.server_stock.stock.presentation.dto.OrderBookResponseDto;
import com.assetmind.server_stock.stock.presentation.dto.OrderBookResponseDto.OrderBookLevelResponse;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@Profile("!prod")
@RequiredArgsConstructor
public class MockOrderBookScheduler {

    private final SimpMessagingTemplate messagingTemplate;
    private final Random random = new Random();

    @Scheduled(fixedRate = 1000)
    public void sendMockOrderBook() {
        String targetStockCode = "005930";
        OrderBookResponseDto mockData = createMockData(targetStockCode);

        // 프론트엔드가 구독 중인 대상 주소로 브로드캐스팅
        String destination = "/topic/orderbook/" + targetStockCode;
        messagingTemplate.convertAndSend(destination, mockData);

        log.info("[MockOrderBookScheduler] 가짜 호가 데이터 전송 완료 -> {}", destination);
    }

    private OrderBookResponseDto createMockData(String stockCode) {
        String currentTime = LocalTime.now().format(DateTimeFormatter.ofPattern("HHmmss"));
        List<OrderBookLevelResponse> levels = new ArrayList<>();

        long basePrice = 270000;
        long totalAsk = 0;
        long totalBid = 0;

        // 1호가 ~ 10호가 가짜 데이터 생성
        for (int i = 1; i <= 10; i++) {
            long askPrice = basePrice + (i * 1000);
            long bidPrice = basePrice - (i * 1000);

            // 매수/매도 호가 잔량은 1000 ~ 5000
            long askSize = 1000 + random.nextInt(4000);
            long bidSize = 1000 + random.nextInt(4000);

            totalAsk += askSize;
            totalBid += bidSize;

            levels.add(
                    OrderBookLevelResponse.builder()
                            .level(i)
                            .askPrice(String.valueOf(askPrice))
                            .askSize(String.valueOf(askSize))
                            .bidPrice(String.valueOf(bidPrice))
                            .bidSize(String.valueOf(bidSize))
                            .build()
            );
        }

        return OrderBookResponseDto.builder()
                .stockCode(stockCode)
                .marketTime(currentTime)
                .totalAskSize(String.valueOf(totalAsk))
                .totalBidSize(String.valueOf(totalBid))
                .levels(levels)
                .build();
    }

}
