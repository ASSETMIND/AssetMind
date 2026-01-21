package com.assetmind.server_stock.market_access.infrastructure.kis;

import static org.assertj.core.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.*;

import com.assetmind.server_stock.market_access.domain.ApiAccessToken;
import com.assetmind.server_stock.market_access.domain.exception.MarketAccessFailedException;
import java.io.IOException;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import okhttp3.mockwebserver.SocketPolicy;
import org.assertj.core.api.Assertions;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClient.Builder;

class KisAuthAdapterTest {

    private MockWebServer mockWebServer;
    private KisAuthAdapter kisAuthAdapter;

    @BeforeEach
    void setUp() throws IOException {
        // Mock 웹서버 실행
        mockWebServer = new MockWebServer();
        mockWebServer.start();

        // 테스트용 Adapter 생성 (MockWebServer 주소를 사용하는 WebClient)
        String baseUrl = String.format("http://localhost:%s", mockWebServer.getPort());
        WebClient.Builder webClientBuilder = WebClient.builder();

        kisAuthAdapter = new KisAuthAdapter(webClientBuilder);

        // 테스트 상황에서는 @Value가 동작하지 않으므로 @Value로 주입받는 private 필드들은 ReflectionTestUtils로 값을 주입
        ReflectionTestUtils.setField(kisAuthAdapter, "baseUrl", baseUrl);
        ReflectionTestUtils.setField(kisAuthAdapter, "appKey", "test-app-key");
        ReflectionTestUtils.setField(kisAuthAdapter, "appSecret", "test-app-secret");
    }

    @AfterEach
    void tearDown() throws IOException {
        mockWebServer.shutdown();
    }

    @Test
    @DisplayName("KIS 접근토큰발급 API 호출 성공 시 올바른 AccessToken을 반환해야한다.")
    void whenFetchTokenSuccess_thenReturnCorrectAccessToken() throws InterruptedException {
        // 가짜 응답 데이터 설정 (KIS 접근토큰발급 API 실제 응답 포맷과 동일)
        mockWebServer.enqueue(new MockResponse()
                .setBody("{\"access_token\": \"fake-jwt-token\", \"token_type\": \"Bearer\", \"expires_in\": 86400, \"access_token_token_expired\": \"2026-01-08 14:00:10\"}")
                .setHeader("Content-type", "application/json"));

        // when
        ApiAccessToken accessToken = kisAuthAdapter.fetchToken();

        // then
        // 응답 데이터 검증
        assertThat(accessToken.tokenValue()).isEqualTo("fake-jwt-token");
        assertThat(accessToken.expiresIn()).isEqualTo(86400);

        // 요청 데이터 검증
        RecordedRequest recordedRequest = mockWebServer.takeRequest();
        assertThat(recordedRequest.getMethod()).isEqualTo("POST"); // HTTP 메서드 확인
        assertThat(recordedRequest.getPath()).isEqualTo("/oauth2/tokenP"); // 요청 경로 확인
        assertThat(recordedRequest.getHeader("Content-type")).contains("application/json"); // 헤더 확인

        String body = recordedRequest.getBody().readUtf8();
        assertThat(body).isEqualTo("{\"grant_type\":\"client_credentials\",\"appkey\":\"test-app-key\",\"appsecret\":\"test-app-secret\"}");
    }

    @Test
    @DisplayName("KIS 접근토큰발급 API 호출 시 API 응답이 4xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.")
    void whenFetchTokenFail400_thenThrowMarketAccessFailedException() {
        // 가짜 응답 데이터 설정
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(400)
                .setBody("{\"error_description\": \"유효하지 않은 AppKey입니다.\", \"error_code\": \"E1234\"}")
                .addHeader("Content-type", "application/json"));

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS API Error");
    }

    @Test
    @DisplayName("KIS 접근토큰발급 API 호출 시 API 응답이 5xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.")
    void whenFetchTokenFail500_thenThrowMarketAccessFailedException() {
        // 가짜 응답 데이터 설정
        mockWebServer.enqueue(new MockResponse()
                .setResponseCode(500)
                .setBody("{\"error_description\": \"서버 내부에서 에러가 발생했습니다.\", \"error_code\": \"E1234\"}")
                .addHeader("Content-type", "application/json"));

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS API Error");
    }

    @Test
    @DisplayName("KIS 서버가 꺼져있어서 연결 거부가 발생하면 MarketAccessFailedException 예외를 던져야한다.")
    void givenShutdownKIS_whenFetchToken_thenThrowMarketAccessFailedException() throws IOException {
        // given
        // 서버를 강제로 꺼서 서버가 꺼진 상황 연출
        mockWebServer.shutdown();

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
    }

    @Test
    @DisplayName("응답 도중 네트워크가 끊기면 MarketAccessFailedException 예외를 던져야한다.")
    void givenNetworkProblem_whenFetchToken_thenThrowMarketAccessFailedException() {
        // given
        // 소켓 정책 설정을 연결 시작하자마자 끊어버리게 만들어서 네트워크 문제를 연출
        mockWebServer.enqueue(new MockResponse()
                .setSocketPolicy(SocketPolicy.DISCONNECT_AT_START));

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
    }
}