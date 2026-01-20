package com.assetmind.server_auth.global.error;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    // Common 에러
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "C001", "서버 내부 오류가 발생했습니다."),
    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "C002", "잘못된 입력값입니다."),


    // User Domain 에러
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, "U001", "존재하지 않는 회원입니다."),
    ALREADY_GET_USER_PERMISSION(HttpStatus.BAD_REQUEST, "U002", "이미 정식 회원입니다."),

    // Jwt 토큰 에러
    INVALID_SIGN_UP_TOKEN(HttpStatus.BAD_REQUEST, "U003", "유효하지 않거나 용도가 잘못된 회원가입 토큰입니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;
}
