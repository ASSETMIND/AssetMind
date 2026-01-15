package com.assetmind.server_auth.user.domain.type;

public enum UserRole {
    /**
     * GUEST: OAuth2 최초 가입 시 부여되는 권한, 본인 인증 X
     * 본인 인증 전이므로 제한된 기능만 접근 가능
     */
    GUEST,

    /**
     * USER: 본인 인증을 완료한 정식 사용자
     * 모든 일반적인 서비스 접근 가능
     */
    USER
}
