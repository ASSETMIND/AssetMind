package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

/**
 * 1분봉 또는 1일봉 캔들을 상위 타임 캔들(1일봉, 3분봉, 5분동, 월봉 등등)으로 압축하는 Service
 */
@Service
public class CandleRollupService {

    /**
     * 1분봉 캔들 리스트를 받아서 원하는 캔들타입으로 롤업
     * @param sourceCandles 원본 캔들 리스트(1분봉 또는 1일봉)
     * @param targetType 만들어낼 목표 캔들 타입 (1일봉, 5분봉, 월봉 ..등등)
     * @return 롤업이 완료된 새로운 캔들 리스트
     */
    public List<OhlcvDto> rollup(List<OhlcvDto> sourceCandles, CandleType targetType) {
        if (sourceCandles == null || sourceCandles.isEmpty()) {
            return List.of();
        }

        // 타겟 시간(3분봉, 5분봉, 월봉 등등)에 맞춰 1분봉 또는 1일봉 캔들들을 그룹핑
        Map<LocalDateTime, List<OhlcvDto>> groupedCandles = sourceCandles.stream()
                .collect(Collectors.groupingBy(candle ->
                        calculateBucketTime(candle.candleTimestamp(), targetType)
                ));

        List<OhlcvDto> rolledUpCandles = new ArrayList<>();

        // 그룹별(3분봉, 5분봉 등등 ..)로 시/고/저/종가/거래량 압축
        for (Map.Entry<LocalDateTime, List<OhlcvDto>> entry : groupedCandles.entrySet()) {
            LocalDateTime bucketTime = entry.getKey();
            List<OhlcvDto> candlesInBucket = entry.getValue();

            // 시간순으로 정렬, 첫 캔들이 시가, 마지막 캔들이 종가
            candlesInBucket.sort(Comparator.comparing(OhlcvDto::candleTimestamp));

            String stockCode = candlesInBucket.getFirst().stockCode();

            // 롤업 계산: 시가는 처음, 종가는 마지막, 고/저가는 Max/Min, 거래량은 합산
            Double openPrice = candlesInBucket.getFirst().openPrice();
            Double closePrice = candlesInBucket.getLast().closePrice();

            Double highPrice = candlesInBucket.stream()
                    .mapToDouble(OhlcvDto::highPrice).max().orElse(openPrice);
            Double lowPrice = candlesInBucket.stream()
                    .mapToDouble(OhlcvDto::lowPrice).min().orElse(openPrice);

            Long totalVolume = candlesInBucket.stream()
                    .mapToLong(OhlcvDto::volume).sum();

            // 압축된 캔들을 DTO로 새로 생성
            OhlcvDto dto = new OhlcvDto(
                    stockCode, bucketTime, openPrice, highPrice, lowPrice, closePrice, totalVolume
            );

            rolledUpCandles.add(dto);
        }

        // 최종 결과를 시간순으로 오름차순 정렬
        rolledUpCandles.sort(Comparator.comparing(OhlcvDto::candleTimestamp));
        return rolledUpCandles;

    }

    // 특정 시간이 어느 캔들 그룹에 속하는지 계산
    private LocalDateTime calculateBucketTime(LocalDateTime timestamp, CandleType targetType) {
        return switch (targetType) {
            // 분봉 (예: 5분봉이면 9:03 -> 9:00 으로 내림)
            // 1분봉: 분 단위만 맞추면 됨
            case MIN_1 -> timestamp.truncatedTo(ChronoUnit.MINUTES); // timestamp를 분단위 까지 맞춤, 2026-03-28 15:30:45 -> 2026-03-28 15:30:00
            // N분봉: 00분을 기준으로 N분에 해당하는 값을 나눈 후 곱한 뒤 N분봉 그룹핑
            case MIN_3, MIN_5, MIN_15 -> {
                int minute = timestamp.getMinute();
                int bucketMinute = (minute / targetType.getWindowMinutes()) * targetType.getWindowMinutes();
                yield timestamp.withMinute(bucketMinute).truncatedTo(ChronoUnit.MINUTES);
            }

            // 일봉: 시간, 분, 초를 모두 버리고 해당 날의 00:00:00으로 맞춤
            case DAY_1 -> timestamp.truncatedTo(ChronoUnit.DAYS);

            // N일봉: 기준일(1970년 1월 1일)로부터 며칠째인지 계산해서 그룹핑
            case DAY_3, DAY_5 -> {
                long epochDay = timestamp.toLocalDate().toEpochDay();
                int daysWindow = targetType.getWindowMinutes() / 1440; // 3일봉(4320), 5일봉(7200)인지 계산
                long bucketEpochDay = (epochDay / daysWindow) * daysWindow;
                yield LocalDate.ofEpochDay(bucketEpochDay).atStartOfDay();
            }

            // 주봉: 그 주의 월요일 00:00:00으로 묶음
            case WEEK_1 -> timestamp.with(DayOfWeek.MONDAY).truncatedTo(ChronoUnit.DAYS);

            // 월봉: 그 달의 1일 00:00:00으로 묶음
            case MONTH_1 -> timestamp.with(TemporalAdjusters.firstDayOfMonth()).truncatedTo(ChronoUnit.DAYS);

            // 년봉: 그 해의 1월 1일 00:00:00으로 묶음
            case YEAR_1 -> timestamp.with(TemporalAdjusters.firstDayOfYear()).truncatedTo(ChronoUnit.DAYS);
        };
    }
}
