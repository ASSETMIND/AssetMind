package com.assetmind.server_stock.global.error;

import com.assetmind.server_stock.global.common.ApiResponse;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import com.assetmind.server_stock.stock.exception.StockNotFoundException;
import jakarta.validation.ConstraintViolationException;
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
     * 입력값의 @Validated 검증 실패 시 발생
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiResponse<Void>> handleConstraintViolationException(ConstraintViolationException e) {
        log.warn("[Global Exception Handler] Validation Error: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail(e.getMessage()));
    }

    /**
     * DTO의 @Valid 검증 실패 시 발생
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleMethodArgumentNotValidException(MethodArgumentNotValidException e) {

        String errorMessage = e.getBindingResult().getAllErrors().get(0).getDefaultMessage();

        log.warn("[Global Exception Handler] DTO Validation Error: {}", errorMessage);

        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail(errorMessage));
    }

    /**
     * 비즈니스 로직 실행 중 발생하는 커스텀 예외 처리
     * (StockNotFoundException, InvalidStockParameterException 등 모두 여기서 잡힘)
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException e) {
        log.warn("[Global Exception Handler] Business Error: {}", e.getMessage());

        ErrorCode errorCode = e.getErrorCode();

        return ResponseEntity
                .status(errorCode.getStatus())
                .body(ApiResponse.fail(errorCode.getMessage()));
    }

    /**
     * 처리하지 못한 모든 시스템 예외 (500 Internal Server Error)
     * 클라이언트에게는 내부의 상세한 에러 내역을 숨기고 공통 메시지만 전달합니다.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e) {
        log.error("[Global Exception Handler] 예상치 못한 서버 에러 발생: {}", e.getMessage(), e);

        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.fail("서버 내부에서 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."));
    }
}
