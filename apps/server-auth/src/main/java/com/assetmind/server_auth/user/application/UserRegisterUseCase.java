package com.assetmind.server_auth.user.application;

import com.assetmind.server_auth.user.application.dto.UserRegisterCommand;
import java.util.UUID;

public interface UserRegisterUseCase {

    /**
     * 이메일 중복 검사
     * @param email - 중복 검사할 이메일
     * @return true: 중복됨(가입불가 X), false: 사용가능한 이메일
     */
    boolean checkEmailDuplicate(String email);

    /**
     * 인증 코드 발송
     * 이메일 중복 체크 포함
     * 인증 코드 생성 및 저장, 메일 발송
     * @param email
     */
    void sendVerificationCode(String email);

    /**
     * 인증 코드 검증
     * 코드가 일치하지 않으면 예외 발생
     * 코드가 일치하면 Redis에서 코드를 삭제,
     * 가입 권한이 담긴 SignUp Token을 발급하여 반환
     * @param email - 인증 코드를 전달한 email
     * @param code - 유저가 입력한 인증 코드
     * @return signUpToken (회원 가입용 임시 토큰)
     */
    String verifyCode(String email, String code);

    /**
     * 최종 회원 가입
     * SignUp Token의 유효성 및 서명을 검증
     * 도메인 생성 및 저장
     * @param cmd - 회원가입 유저 데이터 DTO
     * @return 가입된 유저 ID
     */
    UUID register(UserRegisterCommand cmd);
}
