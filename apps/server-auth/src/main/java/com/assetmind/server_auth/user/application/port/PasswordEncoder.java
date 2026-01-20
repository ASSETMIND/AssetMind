package com.assetmind.server_auth.user.application.port;

/**
 * 비밀번호 암호화 인터페이스 정의
 * 도메인 계층은 어떤 기술을 사용하여 비밀번호를 암호화하는지 모르고
 * 해당 인터페이스의 구현체를 스프링에서 주입해줌(DIP)
 * 이를 통해 도메인의 순수성을 지킬 수 있고 유연하게 확장이 가능
 */
public interface PasswordEncoder {

    /**
     * 평문 비밀번호를 암호화한다.
     * @param rawPassword - 평문 비밀번호
     * @return 암호화된 비밀번호
     */
    String encode(String rawPassword);

    /**
     * 평문 비밀번호와 암호화된 비밀번호가 동일한 비밀번호인지 검증한다.
     * @param rawPassword - 평문 비밀번호
     * @param encodedPassword - 암호화된 비밀번호
     * @return T/F
     */
    boolean matches(String rawPassword, String encodedPassword);

}
