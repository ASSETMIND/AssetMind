package com.assetmind.server_stock.global.error;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    // Stock 에러
    INVALID_STOCK_PARAMETER(HttpStatus.BAD_REQUEST, "S001", "유효하지 않은 입력값 입니다."),
    NOT_FOUND_STOCK(HttpStatus.NOT_FOUND, "S002", "주식 데이터를 찾을 수 없습니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;
}
