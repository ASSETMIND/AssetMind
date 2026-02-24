package com.assetmind.server_auth.user.application.port;

/**
 * 이메일 검증시 사용되는 인증번호 저장소 인터페이스
 * 이메일 인증 코드를 저장하고 조회하는 행위를 정의
 * Service는 인터페이스에만 의존하며,
 * 실제 저장 기술이 무엇인지는 알 필요가 없음 (DIP 원칙)
 */
public interface VerificationCodePort {

    /**
     * 인증 코드 저장 (TTL 포함)
     * @param email - 인증 코드의 키 값, 이메일
     * @param code - 인증 코드
     * @param ttlSeconds - 유효 시간 (초)
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
     * 인증이 성공적으로 완료되면 더 이상 해당 인증 코드를 재사용할 수 없도록
     * 저장소에서 제거
     * @param email - 인증 코드 값의 키 값
     */
    void remove(String email);
}
