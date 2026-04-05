package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.stock.application.dto.ChartResponseDto;
import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1dRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import com.assetmind.server_stock.stock.exception.InvalidChartParameterException;
import java.time.LocalDateTime;
import java.util.List;
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

    public ChartResponseDto getCandles(String stockCode, String timeframe, LocalDateTime endTime, int limit) {
        if (endTime == null) {
            endTime = LocalDateTime.now();
        }

        log.info("[ChartService] 차트 조회 - 종목: {}, 타임프레임: {}, 기준시간: {}, 조회 요청 개수: {}", stockCode, timeframe, endTime, limit);

        List<OhlcvDto> dtoList;

        // 요청 받은 timeframe이 분봉(1m) 테이블로 갈지, 일봉(1d) 테이블로 갈지 결정
        if (isMinuteTimeframe(timeframe)) {
            String intervalString = getMinuteInterval(timeframe);
            dtoList = ohlcv1mRepository.findDynamicMinuteCandles(stockCode, intervalString, endTime, limit);
        } else {
            dtoList = getOhlcvDtoBasedDailyCandles(stockCode, timeframe, endTime, limit);
        }

        List<ChartResponseDto.CandleDto> candleDtos = dtoList.stream()
                .map(dto -> ChartResponseDto.CandleDto.builder()
                        .timestamp(dto.candleTimestamp())
                        .open(String.valueOf(dto.openPrice()))
                        .high(String.valueOf(dto.highPrice()))
                        .low(String.valueOf(dto.lowPrice()))
                        .close(String.valueOf(dto.closePrice()))
                        .volume(String.valueOf(dto.volume()))
                        .build()
                ).toList();

        return ChartResponseDto.builder()
                .stockCode(stockCode)
                .timeframe(timeframe)
                .candles(candleDtos)
                .build();
    }

    private boolean isMinuteTimeframe(String timeframe) {
        return timeframe.endsWith("m") && !timeframe.endsWith("mo");
    }

    private String getMinuteInterval(String timeframe) {
        return switch (timeframe.toLowerCase()) {
            case "1m" -> "1 minute";
            case "3m" -> "3 minutes";
            case "5m" -> "5 minutes";
            case "15m" -> "15 minutes";
            default -> throw new InvalidChartParameterException(ErrorCode.INVALID_CHART_PARAMETER, "지원하지 않는 분봉 타임프레임입니다.");
        };
    }

    private List<OhlcvDto> getOhlcvDtoBasedDailyCandles(String stockCode, String timeframe, LocalDateTime endTime, int limit) {
        return switch (timeframe.toLowerCase()) {
            // 고정 길이 (date_bin 사용)
            case "1d" -> ohlcv1dRepository.findDynamicDailyCandles(stockCode, "1 day", endTime, limit);
            case "3d" -> ohlcv1dRepository.findDynamicDailyCandles(stockCode, "3 days", endTime, limit);
            case "5d" -> ohlcv1dRepository.findDynamicDailyCandles(stockCode, "5 days", endTime, limit);
            case "1w" -> ohlcv1dRepository.findDynamicDailyCandles(stockCode, "1 week", endTime, limit);

            // 가변 길이 (date_trunc 사용)
            case "1mo" -> ohlcv1dRepository.findMonthlyCandles(stockCode, endTime, limit);
            case "1y" -> ohlcv1dRepository.findYearlyCandles(stockCode, endTime, limit);

            default -> throw new InvalidChartParameterException(ErrorCode.INVALID_CHART_PARAMETER, "지원하지 않는 일/주/월/년봉 타임프레임입니다: ");
        };
    }
}
