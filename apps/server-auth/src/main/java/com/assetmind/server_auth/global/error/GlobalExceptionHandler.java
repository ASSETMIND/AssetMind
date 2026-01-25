package com.assetmind.server_auth.global.error;

import com.assetmind.server_auth.global.common.ApiResponse;
import com.assetmind.server_auth.user.exception.InvalidSignUpTokenException;
import com.assetmind.server_auth.user.exception.InvalidVerificationCode;
import com.assetmind.server_auth.user.exception.UserDuplicatedEmail;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 모든 REST Controller 에서 발생하는
 * 예외를 잡아서 처리해주는 곳
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    /**
     * Validation 예외 처리
     * DTO의 @Valid 검증 실패 시 발생 (예: 이메일 형식, null 값 등)
     * -> 400 Bad Request 반환
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidationError(MethodArgumentNotValidException e) {
        String message = e.getMessage();
        log.warn("Validation Error : {}", message);

        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail(message));
    }

    /**
     * 이메일 중복 에외 처리
     * -> 409 Conflict 반환
     */
    @ExceptionHandler(UserDuplicatedEmail.class)
    public ResponseEntity<ApiResponse<Void>> handlerUserDuplicated(UserDuplicatedEmail e) {
        String message = e.getMessage();
        log.warn("Duplicated Email : {}", message);

        return ResponseEntity
                .status(HttpStatus.CONFLICT)
                .body(ApiResponse.fail(message));
    }

    /**
     * 인증 코드 불일치 예외 처리
     * -> 400 Bad Request 반환
     */
    @ExceptionHandler(InvalidVerificationCode.class)
    public ResponseEntity<ApiResponse<Void>> handleInvalidVerificationCode(InvalidVerificationCode e) {
        log.warn("Invalid Verification Code: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail("유효하지 않은 인증 코드입니다."));
    }

    /**
     * 회원가입 토큰 위변조/만료 예외 처리
     * (회원가입 요청 시 토큰이 이상할 때)
     * -> 401 Unauthorized
     */
    @ExceptionHandler(InvalidSignUpTokenException.class)
    public ResponseEntity<ApiResponse<Void>> handleInvalidSignUpToken(InvalidSignUpTokenException e) {
        log.error("Invalid SignUp Token: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.UNAUTHORIZED)
                .body(ApiResponse.fail("유효하지 않거나 만료된 가입 토큰입니다."));
    }

    /**
     * 잘못된 인자 (IllegalArgumentException) 시스템 예외 처리
     * 예: 토큰 내 이메일과 요청 이메일 불일치 등
     * -> 400 Bad Request
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiResponse<Void>> handleIllegalArgument(IllegalArgumentException e) {
        log.warn("Illegal Argument: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail(e.getMessage()));
    }

    /**
     * 예상치 못한 시스템 에러
     * 보안상 상세 에러 내용은 숨기고 로그만 남김
     * -> 500 Internal Server Error
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e) {
        log.error("Unexpected Error Occurred", e); // 스택 트레이스 로깅
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.fail("서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요."));
    }
}
