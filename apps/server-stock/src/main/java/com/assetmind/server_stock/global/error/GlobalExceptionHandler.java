package com.assetmind.server_stock.global.error;

import com.assetmind.server_stock.global.common.ApiResponse;
import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import com.assetmind.server_stock.stock.exception.StockNotFoundException;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
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

    @ExceptionHandler(InvalidStockParameterException.class)
    public ResponseEntity<ApiResponse<Void>> handleInvalidStockParameterException(InvalidStockParameterException e) {
        log.warn("[Global Exception Handler] Invalid Stock Parameter Error: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail(e.getMessage()));
    }

    @ExceptionHandler(StockNotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleStockNotFoundException(StockNotFoundException e) {
        log.warn("[Global Exception Handler] Stock Not Found Error: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.fail(e.getMessage()));
    }
}
