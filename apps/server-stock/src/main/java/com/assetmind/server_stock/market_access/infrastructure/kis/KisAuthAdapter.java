package com.assetmind.server_stock.market_access.infrastructure.kis;

import com.assetmind.server_stock.market_access.domain.ApiAccessToken;
import com.assetmind.server_stock.market_access.domain.ApiApprovalKey;
import com.assetmind.server_stock.market_access.domain.MarketTokenProvider;
import com.assetmind.server_stock.market_access.domain.exception.MarketAccessFailedException;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties.Account;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisApprovalKeyRequest;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisApprovalKeyResponse;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisTokenRequest;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisTokenResponse;
import java.time.Duration;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

/**
 * KIS API를 이용하여(외부 시스템) Auth를 위한 토큰을 가져오는 역할
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class KisAuthAdapter implements MarketTokenProvider {

    private final WebClient.Builder webClientBuilder;
    private final KisProperties kisProperties;

    /**
     * KIS(한국투자증권) 접근토큰발급 API 사용하여 API에 접근하기 위한 accessToken을 받음
     * @return KIS API에 접근하기 위한 accessToken
     */
    @Override
    public ApiAccessToken fetchToken() {
        WebClient webClient = webClientBuilder.baseUrl(kisProperties.getBaseUrl()).build();

        // 일반 REST API 호출용 토큰은 첫 번째 계좌의 키를 사용
        Account firstAccount = kisProperties.getAccounts().getFirst();
        KisTokenRequest request = KisTokenRequest.of(firstAccount.appKey(), firstAccount.appSecret());

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
                    .retryWhen(Retry.backoff(3, Duration.ofSeconds(1)))
                    .block();

            if (response == null) {
                throw new MarketAccessFailedException("KIS API 응답이 비어있습니다.");
            }

            // KIS 응답을 우리 도메인 AccessToken으로 변환해서 반환
            return ApiAccessToken.of(response.accessToken(), response.expiresIn());
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

    /**
     * KIS(한국투자증권) 실시간(웹소켓) 접속키 발급 API를 사용하여
     * 파라미터로 들어온 특정 appkey에 대한 실시간 웹소켓에 접속하기 위한 approval_key를 받음
     * @return 문자열 타입의 approval_key
     */
    @Override
    public ApiApprovalKey fetchApprovalKey(String appKey, String appSecret) {
        WebClient webClient = webClientBuilder.baseUrl(kisProperties.getBaseUrl()).build();

        KisApprovalKeyRequest request = KisApprovalKeyRequest.of(appKey, appSecret);

        try {
            KisApprovalKeyResponse response = webClient.post()
                    .uri("/oauth2/Approval")
                    .bodyValue(request)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, clientResponse ->
                            clientResponse.bodyToMono(String.class)
                                    .flatMap(errorBody -> Mono.error(
                                            new MarketAccessFailedException(
                                                    "KIS WebSocket API Error: " + errorBody)))
                    )
                    .bodyToMono(KisApprovalKeyResponse.class)
                    .retryWhen(Retry.backoff(3, Duration.ofSeconds(1)))
                    .block();

            if (response == null) {
                throw new MarketAccessFailedException("KIS WebSocket API 응답이 비어있습니다.");
            }

            return ApiApprovalKey.from(response.approvalKey());
        } catch (MarketAccessFailedException e) {
            // onStatus()에서 던진 예외를 잡고 로그 출력 후 상위 서비스로 다시 던짐
            log.error("KIS WebSocket 접근 권한 획득 실패: {}", e.getMessage());
            throw e;
        } catch (Exception e) {
            // 네트워크 아웃, 연결 거부 등 onStatus()로 못 잡는 에러
            log.error("KIS WebSocket 접근 권한 획득 중 알 수 없는 에러", e);
            throw new MarketAccessFailedException("KIS 서버 연결 불가, 알 수 없음", e);
        }
    }
}
