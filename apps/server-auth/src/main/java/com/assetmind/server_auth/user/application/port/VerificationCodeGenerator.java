package com.assetmind.server_auth.user.application.port;

/**
 * 인증 코드 생성기
 * 이메일 인증 등에 사용할 랜덤 코드를 생성하는 역할을 정의
 * 테스트 용이성과 랜덤 코드 생성 규칙 변경에도 유연한 대응을 위해 설계
 */
public interface VerificationCodeGenerator {

    /**
     * 인증 코드 생성
     * @return 생성된 인증 코드
     */
    String generate();
}
