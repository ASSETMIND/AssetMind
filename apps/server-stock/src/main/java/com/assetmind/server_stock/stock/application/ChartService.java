package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.global.aspect.LogExecutionTime;
import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1dRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import com.assetmind.server_stock.stock.presentation.dto.ChartResponseDto;
import com.assetmind.server_stock.stock.presentation.dto.ChartResponseDto.CandleDto;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 프론트엔드 차트 렌더링을 위한 N분봉, N일/주/월/년봉 동적 서빙 서비스
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ChartService {
    private final Ohlcv1mRepository ohlcv1mRepository;
    private final Ohlcv1dRepository ohlcv1dRepository;

    @LogExecutionTime
    public ChartResponseDto getNCandles(String stockCode, String timeframe, LocalDateTime endTime, int limit) {

        CandleType candleType = CandleType.from(timeframe);

        int minuteInterval = candleType.getWindowMinutes();

        if (endTime == null) {
            endTime = LocalDateTime.now();
        }

        // 필요한 1분봉 개수 역산 (예: 5분봉 20개 -> 1분봉 100개)
        int requireRawCount = limit * minuteInterval;

        // 필요한 만큼만 1분봉 데이터 조회
        List<OhlcvDto> rawCandles = ohlcv1mRepository.findOneMinuteCandles(stockCode, endTime,
                requireRawCount);

        if (rawCandles.isEmpty()) {
            return ChartResponseDto.builder()
                    .stockCode(stockCode)
                    .timeframe(timeframe)
                    .candles(Collections.emptyList())
                    .build();
        }

        // 1분봉 데이터를 그룹화 하고 N분봉으로 병합
        List<CandleDto> result = rawCandles.stream()
                // N분 단위로 시간을 자르고 그룹화 (예: 5분봉, 10:04 데이터 -> 10:00 그룹)
                .collect(Collectors.groupingBy(
                        candle -> truncateNMinute(candle.candleTimestamp(), minuteInterval)))
                .entrySet().stream()
                // 시간대 별로 묶인(10:00, 10:05, 10:10 ..) 1분봉 리스트를 하나의 N분봉으로 합침
                .map(entry -> {
                    LocalDateTime groupTime = entry.getKey();
                    List<OhlcvDto> group = entry.getValue();

                    // 시가/종가를 위한 시간순(오름차순) 정렬
                    group.sort(Comparator.comparing(OhlcvDto::candleTimestamp));

                    Double open = group.get(0).openPrice();
                    Double close = group.getLast().closePrice();
                    Double high = group.stream().mapToDouble(OhlcvDto::highPrice).max()
                            .orElse(open);
                    Double low = group.stream().mapToDouble(OhlcvDto::lowPrice).min()
                            .orElse(open);
                    Long volume = group.stream().mapToLong(OhlcvDto::volume).sum();

                    return CandleDto.builder()
                            .timestamp(groupTime)
                            .open(String.valueOf(open))
                            .high(String.valueOf(high))
                            .low(String.valueOf(low))
                            .close(String.valueOf(close))
                            .volume(String.valueOf(volume))
                            .build();
                })
                // N분봉으로 그룹화된 결과들을 최신순(내림차순)으로 정렬
                .sorted(Comparator.comparing(CandleDto::timestamp).reversed())
                .limit(limit)
                .toList();

        return ChartResponseDto.builder()
                .stockCode(stockCode)
                .timeframe(timeframe)
                .candles(result)
                .build();
    }

    /**
     * 시간을 N분 단위로 내림
     * 예: time=10:13, n=5 -> return=10:10
     * @param time N분 단위로 내림할 시간
     * @param n N분에 해당되는 분
     * @return N분 단위로 내림 된 시간
     */
    private LocalDateTime truncateNMinute(LocalDateTime time, int n) {
        int minute = time.getMinute();
        int truncatedMinute = (minute / n) * n;
        return time.withMinute(truncatedMinute).withSecond(0).withNano(0);
    }
}
