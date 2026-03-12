package com.assetmind.server_stock.market_access.infrastructure.kis.config;

import java.util.List;
import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * application.yml에 설정되어 있는
 * N개의 계좌에 대한 KIS appkey, appSecret에 대한 값과
 * KIS의 속성들을 한 곳에서 관리하는 클래스
 */
@Getter
@Setter
@Configuration
@ConfigurationProperties(prefix = "kis")
public class KisProperties {

    private long tokenExpiration;
    private String baseUrl;
    private String websocketUrl;

    private List<Account> accounts;

    public record Account(String appKey, String appSecret) {}
}
