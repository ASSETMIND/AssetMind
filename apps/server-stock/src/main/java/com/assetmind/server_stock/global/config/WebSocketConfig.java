package com.assetmind.server_stock.global.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

/**
 * STOMP 프로토콜을 활성화하는 설정 파일
 * 프론트엔드가 접속할 주소와 메시지를 받을 주소를 설정
 */
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // 서버 -> 클라이언트 (구독 경로)
        registry.enableSimpleBroker("/topic");

        // 클라이언트 -> 서버 (발행 경로)
        registry.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        // 연결 주소 - ws://localhost:8080/ws-stock
        registry.addEndpoint("/ws-stock")
                .setAllowedOriginPatterns("*") // 모든 도메인 허용 (CORS)
                .withSockJS(); // WebSocket 미지원 브라우저를 위한 폴백(Fallback) 옵션
    }
}
