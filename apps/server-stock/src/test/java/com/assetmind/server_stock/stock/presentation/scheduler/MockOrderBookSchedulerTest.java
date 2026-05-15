package com.assetmind.server_stock.stock.presentation.scheduler;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.times;

import com.assetmind.server_stock.stock.presentation.dto.OrderBookResponseDto;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.messaging.simp.SimpMessagingTemplate;

@ExtendWith(MockitoExtension.class)
class MockOrderBookSchedulerTest {

    @Mock
    private SimpMessagingTemplate messagingTemplate;

    @InjectMocks
    private MockOrderBookScheduler mockOrderBookScheduler;

    @Test
    @DisplayName("성공: 1초마다 삼성전자 가짜 호가 데이터가 올바른 형식으로 발송되어야 한다.")
    void givenStockCode_whenSendMockOrderBook_thenSendCorrectData() {
        // given
        String expectedStockCode = "005930";
        String expectedDestination = "/topic/orderbook/" + expectedStockCode;

        // 어떤 데이터가 전송되는지 낚아채기 위한 캡터 준비
        ArgumentCaptor<OrderBookResponseDto> captor = ArgumentCaptor.forClass(OrderBookResponseDto.class);

        // when
        mockOrderBookScheduler.sendMockOrderBook();

        // then
        // messagingTemplate의 convertAndSend가 호출되었는지, 경로가 맞는지 검증
        then(messagingTemplate).should(times(1))
                .convertAndSend(eq(expectedDestination), captor.capture());

        // 캡쳐된 실제 전송 데이터를 꺼내서 검증
        OrderBookResponseDto capturedDto = captor.getValue();

        assertThat(capturedDto.stockCode()).isEqualTo(expectedStockCode);
        assertThat(capturedDto.marketTime()).hasSize(6); // HHmmss 포맷 확인
        assertThat(capturedDto.levels()).hasSize(10); // 1~10호가가 다 들어있는지 확인

        // 1호가의 가격과 잔량이 설정한 basePrice 기준으로 적절히 들어갔는지 확인
        assertThat(capturedDto.levels().getFirst().level()).isEqualTo(1);
        assertThat(Long.parseLong(capturedDto.levels().getFirst().askPrice())).isGreaterThan(270000);

        // 총 잔량이 0이 아닌지 확인
        assertThat(Long.parseLong(capturedDto.totalAskSize())).isPositive();
    }
}