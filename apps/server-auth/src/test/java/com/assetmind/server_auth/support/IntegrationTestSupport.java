package com.assetmind.server_auth.support;

import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Testcontainers;

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

    static {
        POSTGRE_SQL_CONTAINER.start();
        REDIS_CONTAINER.start();
    }
}
