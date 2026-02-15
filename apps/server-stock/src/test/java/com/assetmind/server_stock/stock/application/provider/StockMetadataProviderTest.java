package com.assetmind.server_stock.stock.application.provider;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockMetaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.jpa.StockMetaRepository;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * 주식 메타데이터 Provider 단위 테스트
 */
@ExtendWith(MockitoExtension.class)
class StockMetadataProviderTest {

    @Mock
    private StockMetaRepository stockMetaRepository;

    @InjectMocks
    private StockMetadataProvider provider;

    @Test
    @DisplayName("서버 시작 시 DB 데이터를 메모리에 캐싱하고, 조회 시 이름을 반환해야 한다")
    void givenStockMetaData_whenInitAndGetStockName_thenCachingDataAndReturnName() {
        // given
        StockMetaEntity samsung = StockMetaEntity.builder()
                .stockCode("005930")
                .stockName("삼성전자")
                .market("KOSPI")
                .build();

        StockMetaEntity skHynix = StockMetaEntity.builder()
                .stockCode("000660")
                .stockName("SK하이닉스")
                .market("KOSPI")
                .build();

        // Repository가 호출되면 위 2개의 데이터를 반환하도록 설정
        given(stockMetaRepository.findAll()).willReturn(List.of(samsung, skHynix));

        // when
        // @PostConstruct는 단위 테스트에서 자동 실행되지 않으므로 수동으로 호출
        provider.init();

        // then
        // 1. Repository가 실제로 호출되었는지 검증
        verify(stockMetaRepository).findAll();

        // 2. 캐시된 데이터가 올바르게 조회되는지 검증
        assertThat(provider.getStockName("005930")).isEqualTo("삼성전자");
        assertThat(provider.getStockName("000660")).isEqualTo("SK하이닉스");
    }

    @Test
    @DisplayName("캐시에 없는 종목 코드를 조회하면 종목 코드 자체를 반환해야 한다")
    void givenNotCachingData_whenGetStockName_thenStockCode() {
        // given
        // 데이터가 아무것도 없는 상황
        given(stockMetaRepository.findAll()).willReturn(List.of());
        provider.init();

        // when
        String unknownCode = "999999";
        String result = provider.getStockName(unknownCode);

        // then
        // 이름이 없으면 코드가 그대로 나와야 함
        assertThat(result).isEqualTo(unknownCode);
    }
}