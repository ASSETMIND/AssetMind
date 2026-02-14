package com.assetmind.server_stock.global.common;

/**
 * 공통 응답 포맷
 * 모든 API 응답을 이 클래스로 감싸서 응답함
 * @param success - 성공 or 실패
 * @param message - 메시지
 * @param data - 응답 데이터
 * @param <T> - 실제 응답 데이터의 타입
 */
public record ApiResponse<T>(
        boolean success,
        String message,
        T data
) {

    /**
     * 성공 시 데이터만 반환 - 조회 요청
     */
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(true, null, data);
    }

    /**
     * 성공 시 메시지만 반환 - 삭제/수정 요청
     */
    public static <T> ApiResponse<T> success(String message) {
        return new ApiResponse<>(true, message, null);
    }

    /**
     * 성공 시 데이터, 메시지 반환
     */
    public static <T> ApiResponse<T> success(String message, T data) {
        return new ApiResponse<>(true, message, data);
    }

    /**
     * 실패 시 에러 메세지 반환
     */
    public static <T> ApiResponse<T> fail(String message) {
        return new ApiResponse<>(false, message, null);
    }

}
