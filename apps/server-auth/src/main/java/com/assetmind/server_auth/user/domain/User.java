package com.assetmind.server_auth.user.domain;

import com.assetmind.server_auth.global.error.BusinessException;
import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.domain.port.UserIdGenerator;
import com.assetmind.server_auth.user.domain.vo.Password;
import com.assetmind.server_auth.user.domain.vo.SocialID;
import com.assetmind.server_auth.user.domain.vo.UserInfo;
import com.assetmind.server_auth.user.domain.type.UserRole;
import java.util.Objects;
import java.util.UUID;
import lombok.Getter;

/**
 * 우리 서비스의 루트 도메인 유저 객체
 * 모든 유저와 관련된 VO 객체를 조합하여 비즈니스 로직을 수행
 */
@Getter
public class User {
    private final UUID id; // 도메인 객체 식별자

    private final UserInfo userInfo; // 유저 정보
    private Password password; // 유저 비밀번호

    private SocialID socialID; // 소셜 로그인 정보

    // 상태 변경이 가능한 필드
    private UserRole userRole;

    /**
     * 생성자는 private로 제한하여 팩토리 메서드를 통해서만 객체가 생성되도록 강제
     */
    private User(UUID id, UserInfo userInfo, Password password, SocialID socialID, UserRole userRole) {
        this.id = id;
        this.userInfo = userInfo;
        this.password = password;
        this.socialID = socialID;
        this.userRole = userRole;
    }

    /**
     * DB에서 유저 복원시 사용되는 메서드
     * DB의 id과 도메인 객체의 id가 같아야함
     * @param id - DB에 저장된 UUID
     * @param userInfo - DB에 저장된 유저 정보
     * @param socialID - DB에 저장된 소셜 정보
     * @param userRole - DB에 저장된 유저 권한
     * @return DB에 존재하는 User 객체
     */
    public static User withId(UUID id, UserInfo userInfo, Password password, SocialID socialID, UserRole userRole) {
        return new User(id, userInfo, password, socialID, userRole);
    }

    /**
     * 초기 유저 생성시 GUEST(게스트) 역할로 유저를 생성 - 이메일 인증
     * @param userInfo - 유저 정보
     * @param password - 유저 비밀번호
     * @param idGenerator - ID 생성자 인터페이스(ID 생성 방식 정의)
     * @return 유저 객체
     */
    public static User createGuest(UserInfo userInfo, Password password, UserIdGenerator idGenerator) {
        // 유저 정보 및 소셜 정보가 Null 값인지 한번 더 검증
        Objects.requireNonNull(userInfo);
        Objects.requireNonNull(password);

        return new User(idGenerator.generate(), userInfo, password, null, UserRole.GUEST);
    }

    /**
     * 소셜 연동을 통해 유저를 USER(정회원) 역할로 업그레이드
     */
    public void linkSocialAndUpgrade(SocialID socialID) {
        if (this.userRole == UserRole.USER) {
            throw new BusinessException(ErrorCode.ALREADY_GET_USER_PERMISSION);
        }

        if (socialID == null) {
            throw new IllegalArgumentException("연동할 소셜 정보가 없습니다.");
        }
        this.socialID = socialID;
        this.userRole = UserRole.USER;
    }

    public String getEmailValue() {
        return this.userInfo.email().value();
    }

    public String getUsernameValue() {
        return this.userInfo.username().value();
    }

    public String getPasswordValue() {
        return this.password.value();
    }
}
