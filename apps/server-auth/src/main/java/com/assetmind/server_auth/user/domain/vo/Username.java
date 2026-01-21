package com.assetmind.server_auth.user.domain.vo;

/**
 * User의 유저 이름 VO 객체
 * @param value - 서비스에 사용될 유저 이름 값
 */
public record Username(
        String value
) {

    /**
     * username의 값 유효성 검증
     * @param value
     */
    public Username {
        if(value == null || checkLength(value)) {
            throw new IllegalArgumentException("유저 이름은 2자 이상 15자 이하여야 합니다.");
        }
    }

    private boolean checkLength(String value) {
        return value.length() < 2 || value.length() > 15;
    }
}
