package com.assetmind.server_auth.user.domain.vo;

import com.assetmind.server_auth.user.application.port.PasswordEncoder;

/**
 * User의 비밀번호 VO 객체
 * @param value - 암호화된 비밀번호
 */
public record Password(
        String value
) {

    /**
     * DB 로드용 기본 생성자
     * @param value - 암호화된 비밀번호
     */
    public Password {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("비밀번호는 필수입니다.");
        }
    }

    /**
     * 비밀번호 VO객체를 생성하는 정적 팩토리 메서드
     * @param encodedPassword - 암호화된 비밀번호
     * @return 비밀번호 VO 객체
     */
    public static Password from(String encodedPassword) {
        return new Password(encodedPassword);
    }
}
