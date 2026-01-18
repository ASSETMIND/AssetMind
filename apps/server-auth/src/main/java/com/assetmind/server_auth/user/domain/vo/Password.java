package com.assetmind.server_auth.user.domain.vo;

import com.assetmind.server_auth.user.domain.port.PasswordEncoder;

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
     * 길이를 검증하고 암호화를 수행하는 정적 팩토리 메서드
     * @param rawPassword - 비밀번호 평문
     * @param encoder - 평문을 암호화할 encoder
     * @return 암호화된 새 비밀번호
     */
    public static Password create(String rawPassword, PasswordEncoder encoder) {
        if (rawPassword == null || rawPassword.length() < 8 || rawPassword.length() > 20) {
            throw new IllegalArgumentException("비밀번호는 8자 이상 20자 이하여야 합니다.");
        }

        return new Password(encoder.encode(rawPassword));
    }

    /**
     * 입력값인 비밀번호 평문과 현재 암호화된 비밀번호와 동일한지 검증
     * @param rawPassword - 평문 비밀번호
     * @param encoder - 평문을 암호화한 encoder
     * @return T/F
     */
    public boolean match(String rawPassword, PasswordEncoder encoder) {
        return encoder.matches(rawPassword, this.value);
    }


}
