package com.assetmind.server_stock.market_access.infrastructure.kis.config;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * JSON 직렬화/역직렬화 설정
 * 금융 도메인의 핵심 원칙인 "데이터 무결성"을 보장하기 위한 설정
 * 부동소수점(Double/Float) 연산으로 인한 금전적 오차를 원천 차단하는 것이 주 목적
 */
@Configuration
public class JacksonConfig {

    /**
     * 금융 데이터 전용 Object Mapper 등록
     * @return BigDecimal 처리가 강제된 ObjectMapper
     */
    @Bean
    public ObjectMapper objectMapper() {
        return JsonMapper.builder()
                // JSON의 실수형(Float) 데이터를 무조건 BigDecimal로 역직렬화한다.
                // (이유: 0.1 + 0.2 != 0.3 부동소수점 이슈 방지)
                .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
                // DTO에 정의되지 않은 필드가 JSON에 있어도 에러를 내지 않고 무시한다.
                // (이유: 증권사 API 스펙이 예고 없이 변경되어 필드가 추가되더라도 장애를 막기 위함)
                .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                .build();
    }
}
