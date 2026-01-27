package com.assetmind.server_auth.support;

import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * TestContainer를 통해서 도커 컨테이너를 띄우고 스프링에 포트를 알려주는 추상 클래스
 */
@SpringBootTest // 통합 테스트
@ActiveProfiles("test") // application-test.yml
@Testcontainers // 컨테이너 관리 활성화
@AutoConfigureMockMvc
public abstract class IntegrationTestSupport {

    /**
     * PostgreSQL 컨테이너 정의
     */
    static final PostgreSQLContainer<?> POSTGRES_CONTAINER = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("testdb")
            .withUsername("test")
            .withPassword("test");

    /**
     * Redis 컨테이너 정의
     * TestContainer 라이브러리에 Redis 컨테이너가 없다.
     * 하지만, Redis 컨테이너를 위한 라이브러리를 따로 추가하지 않고
     * GenericContainer에 이미지를 명시하여서 Redis 이미지를 컨테이너로 띄움
     */
    static final int REDIS_PORT = 6379;
    static final GenericContainer<?> REDIS_CONTAINER = new GenericContainer<>("redis:alpine")
            .withExposedPorts(REDIS_PORT);

    static {
        POSTGRES_CONTAINER.start();
        REDIS_CONTAINER.start();
    }

    /**
     * TestContainer가 스프링에게 랜덤으로 할당한 컨테이너 포트를
     * application-test.yml 값에 매핑
     * @param registry
     */
    @DynamicPropertySource
    static void overrideProps(DynamicPropertyRegistry registry) {
        // PostgreSQL 설정
        registry.add("spring.datasource.url", POSTGRES_CONTAINER::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES_CONTAINER::getUsername);
        registry.add("spring.datasource.password", POSTGRES_CONTAINER::getPassword);

        // Redis 설정
        registry.add("spring.data.redis.host", REDIS_CONTAINER::getHost);
        registry.add("spring.data.redis.port", () -> REDIS_CONTAINER.getMappedPort(REDIS_PORT));
    }
}
