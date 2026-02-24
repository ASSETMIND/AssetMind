package com.assetmind.server_stock.support;

import org.junit.jupiter.api.BeforeEach;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.ActiveProfiles;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;

@SpringBootTest // 통합 테스트
@ActiveProfiles("test") // application-test.yml
@AutoConfigureMockMvc
public abstract class IntegrationTestSupport {

    @ServiceConnection(name = "postgres")
    static final PostgreSQLContainer<?> POSTGRE_SQL_CONTAINER = new PostgreSQLContainer<>("postgres:16-alpine");

    static final int REDIS_PORT = 6379;

    @ServiceConnection(name = "redis")
    static final GenericContainer<?> REDIS_CONTAINER = new GenericContainer<>("redis:alpine")
            .withExposedPorts(REDIS_PORT);

    private static final MockKisServer MOCK_KIS_SERVER = new MockKisServer(8089);

    static {
        POSTGRE_SQL_CONTAINER.start();
        REDIS_CONTAINER.start();
        MOCK_KIS_SERVER.start();
    }

    // 각 테스트 시작 전에 Mock 서버 상태를 초기화
    @BeforeEach
    void resetMockKisServer() {
        MOCK_KIS_SERVER.reset();
    }
}
