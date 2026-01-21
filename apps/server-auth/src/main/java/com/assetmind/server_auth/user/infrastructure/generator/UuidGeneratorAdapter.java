package com.assetmind.server_auth.user.infrastructure.generator;

import com.assetmind.server_auth.user.application.port.UserIdGenerator;
import java.util.UUID;
import org.springframework.stereotype.Component;

/**
 * ID 생성 어댑터
 * IdGenerator 인터페이스의 구현체로써
 * 자바의 UUID 라이브러리를 사용하여 고유 식별자를 생성
 */
@Component
public class UuidGeneratorAdapter implements UserIdGenerator {

    @Override
    public UUID generate() {
        return UUID.randomUUID();
    }
}
