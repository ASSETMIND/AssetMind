package com.assetmind.server_auth.user.infrastructure.id;

import java.util.UUID;
import org.springframework.stereotype.Component;
import org.springframework.util.IdGenerator;

/**
 * ID 생성 어댑터
 * IdGenerator 인터페이스의 구현체로써
 * 자바의 UUID 라이브러리를 사용하여 고유 식별자를 생성
 */
@Component
public class UuidGeneratorAdapter implements IdGenerator {

    @Override
    public UUID generateId() {
        return UUID.randomUUID();
    }
}
