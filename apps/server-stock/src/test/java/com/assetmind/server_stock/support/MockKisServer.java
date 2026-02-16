package com.assetmind.server_stock.support;

import static com.github.tomakehurst.wiremock.client.WireMock.*;

import com.github.tomakehurst.wiremock.WireMockServer;
import com.github.tomakehurst.wiremock.client.WireMock;

/**
 * KIS(한국투자증권) Mock API 서버
 *
 * 통합 테스트 시 실제 API과 통신하지 않고,
 * 로컬 환경에서 HTTP 요청을 받아 미리 정의된 가짜 응답(Stub)을 내려주는 역할
 */
public class MockKisServer {

    private final WireMockServer wireMockServer;

    public MockKisServer(int port) {
        this.wireMockServer = new WireMockServer(port);
    }

    public void start() {
        if (!wireMockServer.isRunning()) {
            wireMockServer.start();
            WireMock.configureFor("localhost", wireMockServer.port());
        }

        reset();
    }

    public void stop() {
        if (wireMockServer.isRunning()) {
            wireMockServer.stop();
        }
    }

    /**
     * 매 테스트마다 Mock 서버 상태를 깨끗하게 비우고 기본 성공 응답을 다시 세팅
     */
    public void reset() {
        wireMockServer.resetAll(); // 기존에 설정된 시나리오 제거
        setupTokenBehavior(); // 토큰 발급 성공 시나리오

    }

    private void setupTokenBehavior() {
        // [REST] OAuth 토큰 발급 성공 스텁 (POST /oauth2/tokenP)
        wireMockServer.stubFor(post(urlPathEqualTo("/oauth2/tokenP"))
                .willReturn(aResponse()
                        .withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody("""
                                {
                                    "access_token": "dummy_access_token",
                                    "token_type": "Bearer",
                                    "expires_in": 3600
                                }
                                """)));

        // [WebSocket] 접속키(Approval Key) 발급 성공 스텁 (POST /oauth2/Approval)
        wireMockServer.stubFor(post(urlPathEqualTo("/oauth2/Approval"))
                .willReturn(aResponse()
                        .withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody("""
                            {
                                "approval_key": "dummy_approval_key_from_wiremock"
                            }
                            """)));
    }

}
