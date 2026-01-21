package com.assetmind.server_auth.user.infrastructure.generator;

import com.assetmind.server_auth.user.application.port.VerificationCodeGenerator;
import java.security.SecureRandom;
import org.springframework.stereotype.Component;

/**
 * SecureRandom 기반 인증 코드 생성 구현체
 * Java의 SecureRandom을 사용하여 예측 불가능한 6자리 난수를 생성
 */
@Component
public class RandomVerificationCodeAdapter implements VerificationCodeGenerator {

    // 매번 생성하지 않고 재사용
    private static final SecureRandom secureRandom = new SecureRandom();


    @Override
    public String generate() {
        // 100000 ~ 999999 사이의 난수 생성
        int code = 100000 + secureRandom.nextInt(900000);
        return String.valueOf(code);
    }
}
