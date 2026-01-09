package com.assetmind.server_stock.market_access.infrastructure.config;

import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.KisWebSocketHandler;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;

/**
 * KIS WebSocket에 관한 설정
 */
@Configuration
public class KisWebSocketConfig {

    /**
     * WebSocketClient 인터페이스의 구현체로 'StandardWebSocketClient' 를 스프링 빈 등록
     * StandardWebSocketClient는 내부적으로 톰캣, 제티 같은 내장 WAS의 웹소켓 엔진을 사용하여 연결을 맺어줌
     */
    @Bean
    public WebSocketClient webSocketClient() {
        return new StandardWebSocketClient();
    }

    /**
     * 서버 애플리케이션 시작시 KIS WebSocket에 연결 시도
     * @param handler
     * @return
     */
    @Bean
    public CommandLineRunner initKisWebSocket(KisWebSocketHandler handler) {
        return args -> handler.connect();
    }
}
