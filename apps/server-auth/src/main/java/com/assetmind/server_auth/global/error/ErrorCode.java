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
    USER_DUPLICATED_EMAIL(HttpStatus.CONFLICT, "U003", "중복된 이메일입니다."),
    INVALID_VERIFICATION_CODE(HttpStatus.BAD_REQUEST, "U004", "유효하지 않은 인증 코드입니다."),
    INCORRECT_PASSWORD(HttpStatus.UNAUTHORIZED, "U005", "비밀번호가 맞지 않습니다."),

    // Jwt 토큰 에러
    INVALID_SIGN_UP_TOKEN(HttpStatus.BAD_REQUEST, "T001", "유효하지 않거나 용도가 잘못된 회원가입 토큰입니다."),
    EXPIRED_TOKEN(HttpStatus.UNAUTHORIZED, "T003", "토큰이 만료되었습니다."),
    INVALID_TOKEN_SIGNATURE(HttpStatus.UNAUTHORIZED, "T004", "토큰 서명이 유효하지 않습니다."),
    INVALID_TOKEN_TYPE(HttpStatus.UNAUTHORIZED, "T004", "잘못된 토큰 타입입니다."),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "T005", "유효하지 않은 토큰입니다."),
    INVALID_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "T006", "유효하지 않거나 만료된 리프레시 토큰입니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;
}
