package com.assetmind.server_auth.user.application.port;

/**
 * 이메일 검증시 사용되는 인증번호 저장소 인터페이스
 */
public interface VerificationCodePort {

    /**
     * 인증 코드 저장 (TTL 포함)
     * @param email - 인증 코드의 키 값, 이메일
     * @param code - 인증 코드
     * @param ttlSeconds - 유효 시간
     */
    void save(String email, String code, long ttlSeconds);

    /**
     * 인증 코드 조회
     * @param email - 인증 코드 값의 키 값
     * @return 인증 코드 값
     */
    String getCode(String email);

    /**
     * 인증 코드 삭제
     * @param email - 인증 코드 값의 키 값
     */
    void remove(String email);
}
