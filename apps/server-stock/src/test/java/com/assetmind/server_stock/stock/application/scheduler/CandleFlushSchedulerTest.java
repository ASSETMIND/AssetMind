package com.assetmind.server_stock.stock.application.scheduler;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.assetmind.server_stock.stock.application.CandleRollupService;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import com.assetmind.server_stock.stock.domain.repository.CandleRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1dRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
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

    @Mock
    private Ohlcv1dRepository ohlcv1dRepository;

    @Mock
    private StockMetadataProvider stockMetadataProvider;

    @Mock
    private CandleRollupService candleRollupService;

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

    @Test
    @DisplayName("1일봉 스케줄러 실행 시, 모든 종목의 1분봉을 1일봉으로 롤업하여 DB에 일괄 저장한다.")
    void givenStockCodesAnd1mCandles_whenFlushDailyCandles_thenRollupAndSaveAll() {
        // Given
        LocalDate today = LocalDate.now();
        List<String> stockCodes = List.of("005930", "000660"); // 삼성전자, SK하이닉스 2개 종목 세팅

        when(stockMetadataProvider.getAllStockCodes()).thenReturn(stockCodes);

        // 삼성전자 데이터 세팅
        List<OhlcvDto> samsung1mCandles = List.of(new OhlcvDto("005930", LocalDateTime.now(), 1.0, 2.0, 0.5, 1.5, 100L));
        List<OhlcvDto> samsung1dCandle = List.of(new OhlcvDto("005930", today.atStartOfDay(), 1.0, 2.0, 0.5, 1.5, 100L));

        when(ohlcv1mRepository.findCandlesByDate("005930", today)).thenReturn(samsung1mCandles);
        when(candleRollupService.rollup(samsung1mCandles, CandleType.DAY_1)).thenReturn(samsung1dCandle);

        // SK하이닉스 데이터 세팅
        List<OhlcvDto> hynix1mCandles = List.of(new OhlcvDto("000660", LocalDateTime.now(), 5.0, 6.0, 4.0, 5.5, 200L));
        List<OhlcvDto> hynix1dCandle = List.of(new OhlcvDto("000660", today.atStartOfDay(), 5.0, 6.0, 4.0, 5.5, 200L));

        when(ohlcv1mRepository.findCandlesByDate("000660", today)).thenReturn(hynix1mCandles);
        when(candleRollupService.rollup(hynix1mCandles, CandleType.DAY_1)).thenReturn(hynix1dCandle);

        // When
        candleFlushScheduler.flushDailyCandles();

        // Then: 2개 종목의 롤업 결과가 하나의 리스트로 합쳐져서 saveAll로 들어갔는지 검증
        List<OhlcvDto> expectedSavedCandles = new ArrayList<>();
        expectedSavedCandles.addAll(samsung1dCandle);
        expectedSavedCandles.addAll(hynix1dCandle);

        verify(ohlcv1dRepository, times(1)).saveAll(expectedSavedCandles);
    }

    @Test
    @DisplayName("조회된 종목이 없으면 빈 리스트로 saveAll을 호출하며 에러 없이 종료된다.")
    void givenNoStockCodes_whenFlushDailyCandles_thenSaveEmptyList() {
        // Given
        when(stockMetadataProvider.getAllStockCodes()).thenReturn(List.of());

        // When
        candleFlushScheduler.flushDailyCandles();

        // Then
        verify(ohlcv1mRepository, never()).findCandlesByDate(anyString(), any(LocalDate.class));
        verify(candleRollupService, never()).rollup(any(), any());
        verify(ohlcv1dRepository, times(1)).saveAll(List.of()); // 빈 리스트 저장 호출 확인
    }
}