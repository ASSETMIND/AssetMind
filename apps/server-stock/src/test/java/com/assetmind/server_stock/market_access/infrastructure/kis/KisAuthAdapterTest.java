package com.assetmind.server_stock.market_access.infrastructure.kis;

import static org.assertj.core.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.*;

import com.assetmind.server_stock.market_access.domain.ApiAccessToken;
import com.assetmind.server_stock.market_access.domain.ApiApprovalKey;
import com.assetmind.server_stock.market_access.domain.exception.MarketAccessFailedException;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties.Account;
import java.io.IOException;
import java.util.List;
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
    private KisProperties kisProperties;

    @BeforeEach
    void setUp() throws IOException {
        // Mock 웹서버 실행
        mockWebServer = new MockWebServer();
        mockWebServer.start();

        // 테스트용 Adapter 생성 (MockWebServer 주소를 사용하는 WebClient)
        String baseUrl = String.format("http://localhost:%s", mockWebServer.getPort());
        WebClient.Builder webClientBuilder = WebClient.builder();

        kisProperties = new KisProperties();
        kisProperties.setBaseUrl(baseUrl);
        kisProperties.setAccounts(List.of(
                new Account("test-app-key-1", "test-app-secret-1"),
                new Account("test-app-key-2", "test-app-secret-2")
        ));

        kisAuthAdapter = new KisAuthAdapter(webClientBuilder, kisProperties);
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

        // 요청 데이터 검증 (대표 계좌인 1번 키가 잘 들어갔는지 확인)
        RecordedRequest recordedRequest = mockWebServer.takeRequest();
        assertThat(recordedRequest.getMethod()).isEqualTo("POST"); // HTTP 메서드 확인
        assertThat(recordedRequest.getPath()).isEqualTo("/oauth2/tokenP"); // 요청 경로 확인
        assertThat(recordedRequest.getHeader("Content-type")).contains("application/json"); // 헤더 확인

        String body = recordedRequest.getBody().readUtf8();
        assertThat(body).isEqualTo("{\"grant_type\":\"client_credentials\",\"appkey\":\"test-app-key-1\",\"appsecret\":\"test-app-secret-1\"}");
    }

    @Test
    @DisplayName("KIS 접근토큰발급 API 호출 시 API 응답이 4xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.")
    void whenFetchTokenFail400_thenThrowMarketAccessFailedException() {
        // 가짜 응답 데이터 설정
        enqueueErrorResponse(4, 400, "{\"error_description\": \"유효하지 않은 AppKey입니다.\", \"error_code\": \"E1234\"}");

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
    }

    @Test
    @DisplayName("KIS 접근토큰발급 API 호출 시 API 응답이 5xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.")
    void whenFetchTokenFail500_thenThrowMarketAccessFailedException() {
        // 가짜 응답 데이터 설정
        enqueueErrorResponse(4, 500, "{\"error_description\": \"서버 내부에서 에러가 발생했습니다.\", \"error_code\": \"E1234\"}");

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
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
        // 재시도 3회 정책 포함해서 총 4회의 에러 응답을 반환하도록 연출
        for (int i = 0; i < 4; i++) {
            mockWebServer.enqueue(new MockResponse()
                    .setSocketPolicy(SocketPolicy.DISCONNECT_AT_START));
        }

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchToken())
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
    }

    @Test
    @DisplayName("KIS 접속키(Approval Key) 발급 API 성공 시 올바른 ApprovalKey를 반환해야한다.")
    void whenFetchApprovalKeySuccess_thenReturnCorrectApproveKey() throws InterruptedException {
        // KIS 실시간 (웹소켓) 접속키 발급 API 실제 응답 포맷
        mockWebServer.enqueue(new MockResponse()
                .setBody("{\"approval_key\": \"test-approval-key-123\"}")
                .setHeader("Content-type", "application/json"));

        // when
        String targetAppKey = "target-ws-key";
        String targetAppSecret = "target-ws-secret";
        ApiApprovalKey approvalKey = kisAuthAdapter.fetchApprovalKey(targetAppKey, targetAppSecret);

        // then
        // 응답 데이터 검증
        assertThat(approvalKey).isNotNull();
        assertThat(approvalKey.value()).isEqualTo("test-approval-key-123");

        // 요청 데이터 검증
        RecordedRequest recordedRequest = mockWebServer.takeRequest();
        assertThat(recordedRequest.getMethod()).isEqualTo("POST"); // HTTP 메서드 확인
        assertThat(recordedRequest.getPath()).isEqualTo("/oauth2/Approval"); // 요청 경로 확인
        assertThat(recordedRequest.getHeader("Content-type")).contains("application/json"); // 헤더 확인

        String body = recordedRequest.getBody().readUtf8();
        assertThat(body).contains("\"appkey\":\"" + targetAppKey + "\"");
        assertThat(body).contains("\"secretkey\":\"" + targetAppSecret + "\"");
    }

    @Test
    @DisplayName("KIS 접속키(Approval Key) 발급 API 호출 시 API 응답이 4xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.")
    void whenFetchApprovalKey400_thenThrowMarketAccessFailedException() {
        // 가짜 응답 데이터 설정
        enqueueErrorResponse(4, 400, "{\"error_description\": \"유효하지 않은 AppKey입니다.\", \"error_code\": \"E1234\"}");

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchApprovalKey("dummy", "dummy"))
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
    }

    @Test
    @DisplayName("KIS 접속키(Approval Key) 발급 API 호출 시 API 응답이 5xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.")
    void whenFetchApprovalKey500_thenThrowMarketAccessFailedException() {
        // 가짜 응답 데이터 설정
        enqueueErrorResponse(4, 500, "{\"error_description\": \"서버 내부에서 에러가 발생했습니다.\", \"error_code\": \"E1234\"}");

        // when & then
        assertThatThrownBy(() -> kisAuthAdapter.fetchApprovalKey("dummy", "dummy"))
                .isInstanceOf(MarketAccessFailedException.class)
                .hasMessageContaining("KIS 서버 연결 불가");
    }

    /**
     * 파라미터로 지정도니 횟수 만큼 MockWebServer에 에러 응답을 채워 넣는다.
     */
    private void enqueueErrorResponse(int count, int statusCode, String body) {
        for (int i = 0; i < count; i++) {
            mockWebServer.enqueue(new MockResponse()
                    .setResponseCode(statusCode)
                    .setBody(body)
                    .addHeader("Content-type", "application/json"));
        }
    }
}