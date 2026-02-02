package com.assetmind.server_auth.user.application.port;

/**
 * 이메일 전송을 정의하는 인터페이스
 */
public interface EmailSendPort {

    /**
     * 이메일 발송 요청
     * @param targetAddress - 목적지 이메일
     * @param title - 이메일의 제목
     * @param content - 이메일의 내용
     */
    void sendEmail(String targetAddress, String title, String content);
}
