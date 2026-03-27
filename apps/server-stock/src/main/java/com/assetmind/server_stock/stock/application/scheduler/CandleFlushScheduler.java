package com.assetmind.server_stock.stock.application.scheduler;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import com.assetmind.server_stock.stock.domain.repository.CandleRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class CandleFlushScheduler {

    // 1분봉 가져올 캔들 레포지토리
    private final CandleRepository candleRepository;

    // 1분봉 저장 어댑터
    private final Ohlcv1mRepository ohlcv1mRepository;

    private static final DateTimeFormatter MINUTE_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmm");

    /**
     * 1분봉 저장 작업, 평일 주식시장 시간에만 실행
     */
    @Scheduled(cron = "0 * 9-15 * * MON-FRI")
    public void flush1MinuteCandles() {
        LocalDateTime targetTimeObj = LocalDateTime.now().minusMinutes(1);
        String targetTime = targetTimeObj.format(MINUTE_FORMATTER);

        log.info("[CandleFlushScheduler] {} 1분봉 캔들 Flush 시작", targetTime);

        List<OhlcvDto> flushedCandles = candleRepository.flushCandles(targetTime, CandleType.MIN_1);

        if (!flushedCandles.isEmpty()) {
            ohlcv1mRepository.saveAll(flushedCandles);
            log.info("[CandleFlushScheduler] 1분봉 캔들 {}개 DB(ohlcv_1m) 저장 완료", flushedCandles.size());
        } else {
            log.info("[CandleFlushScheduler] 1분봉 캔들 수집된 데이터가 없습니다.");
        }
    }

    /**
     * 1일봉 롤업 작업, 평일 장 마감 이후인 16시 30초에 실행
     * 1분봉 스케줄러가 16시에 끝나므로 30초 여유를 둬서 1일봉 스케줄러는 16시 30초에 실행하도록 계획
     */
    @Scheduled(cron = "30 00 16 * * MON-FRI")
    public void flushDailyCandles() {
        // TODO: 1일봉 롤업 로직
    }
}
