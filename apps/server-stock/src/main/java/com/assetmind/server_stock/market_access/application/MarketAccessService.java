package com.assetmind.server_stock.market_access.application;

import com.assetmind.server_stock.market_access.domain.ApiAccessToken;
import com.assetmind.server_stock.market_access.domain.MarketTokenProvider;
import com.assetmind.server_stock.market_access.domain.exception.MarketAccessFailedException;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/**
 * 토큰을 관리하고 제공하는 정책을 담당
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MarketAccessService {
    private final MarketTokenProvider marketTokenProvider;

    // API을 사용하는 Http Request 요청을 위한 accessToken 읽기 스레드,
    // 주기적인 토큰 갱신을 위해 읽기 작업을 하는 스케줄러 스레드
    // 여러 스레드가 접근하므로 가시성을 보장해주는 즉 각 스레드에 할당된 CPU에 캐싱하는 것이 아닌
    // 바로 메인 메모리에 접근해서 데이터의 정합성을 지키는 volatile 사용
    private volatile String cachedAccessToken;

    // 앱 시작 시점에 토큰을 한번 받아옴
    @PostConstruct
    public void init() {
        log.info(">>> Market Access 모듈 초기화: 최초 토큰 발급 시도");
        refreshAccessToken();
    }

    /**
     * 다른 도메인이나 모듈이 해당 메서드를 통해서 시장 API에 접근하기 위한 토큰을 받음
     * @return 캐싱된 토큰
     */
    public String getAccessToken() {
        if (cachedAccessToken == null) {
            log.warn("캐시된 토큰이 없습니다. 즉시 발급을 시도합니다.");
            refreshAccessToken();
        }
        return cachedAccessToken;
    }

    /**
     * KIS 토큰 유효기간인 24시간 만료 전에 미리 갱신
     * 안전한 시간을 위해 6시간 마다 갱신
     */
    @Scheduled(fixedRate = 6 * 60 * 60 * 1000)
    public void scheduleTokenRefresh() {
        log.info(">>> 토큰 자동 갱신 스케줄러 실행");
        refreshAccessToken();
    }

    /**
     * 실제 시장 API에 접근하기 위한 토큰 발급 Adapter를 호출하여
     * 토큰을 갱신하고 메모리에 저장(캐싱)
     * 토큰을 발급하는 도중에 다른 스레드가 끼어들수 없도록(Lock) synchronized 하여
     * 캐싱된 토큰의 원자성을 보장
     */
    private synchronized void refreshAccessToken() {
        try {
            ApiAccessToken apiAccessToken = marketTokenProvider.fetchToken();
            this.cachedAccessToken = apiAccessToken.tokenValue();
            log.info(">>> 토큰 갱신 완료 (만료시간: {}초)", apiAccessToken.expiresIn());
        } catch (MarketAccessFailedException e) {
            log.error(">>> 토큰 갱신 실퍠! (기존 토큰 유지)", e);
        }
    }
}
