package com.assetmind.server_stock.stock.application.scheduler;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import com.assetmind.server_stock.stock.domain.repository.CandleRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CandleFlushSchedulerTest {

    @Mock
    private CandleRepository candleRepository;

    @Mock
    private Ohlcv1mRepository ohlcv1mRepository;

    @InjectMocks
    private CandleFlushScheduler candleFlushScheduler;

    @Test
    @DisplayName("Redis에서 Flush된 캔들 데이터가 존재하면 DB에 저장(saveAll) 메서드를 호출한다.")
    void givenFlushedCandles_whenFlush1MinuteCandles_thenCallsSaveAll() {
        // Given
        OhlcvDto dummyDto = new OhlcvDto(
                "005930", LocalDateTime.now(),
                75000.0, 76000.0, 74000.0, 75500.0, 1000L
        );
        List<OhlcvDto> dummyList = List.of(dummyDto);

        // Redis가 데이터를 반환한다고 가정
        when(candleRepository.flushCandles(anyString(), eq(CandleType.MIN_1))).thenReturn(dummyList);

        // When
        candleFlushScheduler.flush1MinuteCandles();

        // Then: DB 저장 어댑터의 saveAll이 정확히 1번 호출되었는지 검증
        verify(ohlcv1mRepository, times(1)).saveAll(dummyList);
    }

    @Test
    @DisplayName("Redis에서 Flush된 캔들 데이터가 없으면(빈 리스트) DB에 저장 메서드를 호출하지 않는다.")
    void givenEmptyCandles_whenFlush1MinuteCandles_thenDoesNotCallSaveAll() {
        // Given
        // Redis가 빈 리스트를 반환한다고 가정
        when(candleRepository.flushCandles(anyString(), eq(CandleType.MIN_1))).thenReturn(List.of());

        // When
        candleFlushScheduler.flush1MinuteCandles();

        // Then: 저장 로직(saveAll)이 호출되지 않는지 검증
        verify(ohlcv1mRepository, never()).saveAll(any());
    }
}