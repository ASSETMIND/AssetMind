package com.assetmind.server_stock.market_access.infrastructure.kis;

import com.assetmind.server_stock.market_access.domain.ApiAccessToken;
import com.assetmind.server_stock.market_access.domain.MarketTokenProvider;
import com.assetmind.server_stock.market_access.domain.exception.MarketAccessFailedException;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisTokenRequest;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisTokenResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

/**
 * KIS API를 이용하여(외부 시스템) Auth를 위한 토큰을 가져오는 역할
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class KisAuthAdapter implements MarketTokenProvider {

    private final WebClient.Builder webClientBuilder;

    @Value("${kis.base-url}")
    private String baseUrl;

    @Value("${kis.app-key}")
    private String appKey;

    @Value("${kis.app-secret}")
    private String appSecret;

    /**
     * KIS(한국투자증권) 접근토큰발급 API 사용하여 API에 접근하기 위한 accessToken을 받음
     * @return KIS API에 접근하기 위한 accessToken
     */
    @Override
    public ApiAccessToken fetchToken() {
        WebClient webClient = webClientBuilder.baseUrl(baseUrl).build();

        KisTokenRequest request = KisTokenRequest.createKisTokenReq(appKey, appSecret);

        try {
            // 접근토큰발급 API
            KisTokenResponse response = webClient.post()
                    .uri("/oauth2/tokenP")
                    .bodyValue(request)
                    .retrieve()
                    // API 응답 상태 코드가 error(4xx, 5xx) 일 때 처리
                    .onStatus(HttpStatusCode::isError, clientResponse ->
                        clientResponse.bodyToMono(String.class)
                                .flatMap(errorBody -> Mono.error(new MarketAccessFailedException("KIS API Error: " + errorBody)))
                    )
                    .bodyToMono(KisTokenResponse.class)
                    .block();

            if (response == null) {
                throw new MarketAccessFailedException("KIS API 응답이 비어있습니다.");
            }

            // KIS 응답을 우리 도메인 AccessToken으로 변환해서 반환
            return ApiAccessToken.createApiAccessToken(response.accessToken(), response.expiresIn());
        } catch (MarketAccessFailedException e) {
            // onStatus()에서 던진 예외를 잡고 로그 출력 후 상위 서비스로 다시 던짐
            log.error("KIS API 접근 권한 획득 실패: {}", e.getMessage());
            throw e;
        } catch (Exception e) {
            // 네트워크 아웃, 연결 거부 등 onStatus()로 못 잡는 에러
            log.error("KIS API 접근 권한 획득 중 알 수 없는 에러", e);
            throw new MarketAccessFailedException("KIS 서버 연결 불가, 알 수 없음", e);
        }
    }
}
