package com.assetmind.server_stock.market_access.infrastructure.kis.config;

import jakarta.websocket.WebSocketContainer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

@Configuration
@EnableScheduling
public class KisWebSocketConfig {

    /**
     * 웹소켓 Ping과 재접속 스케줄링을 담당할 스케줄러
     */
    @Bean
    public ThreadPoolTaskScheduler taskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();

        // 재접속 전용 스케줄러 1개
        scheduler.setPoolSize(1);

        scheduler.setThreadNamePrefix("Kis-Socket-Scheduler");

        scheduler.initialize();
        return scheduler;
    }
}
