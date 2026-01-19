package com.assetmind.server_auth.user.infrastructure.mail;

import com.assetmind.server_auth.user.domain.port.EmailSendPort;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * 이메일 전송을 정의하는 인터페이스(EmailSendPort)의 구현체
 * 해당 구현체는 Google SMTP를 이용하여 메일을 전송
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class EmailSenderAdapter implements EmailSendPort {

    private final JavaMailSender javaMailSender;

    /**
     * 비동기적으로 메일을 발송하는 메서드
     * 별도의 스레드로 메일을 발송
     * @param targetAddress - 목적지 이메일
     * @param title - 이메일의 제목
     * @param content - 이메일의 내용
     */
    @Override
    @Async
    public void sendEmail(String targetAddress, String title, String content) {
        log.info("이메일 발송 시작 - To: {}", targetAddress);

        try {
            // 추후 본인인증 메일에 HTML 포맷이 필요할 것 같아서
            // 텍스트만 보내는 SimpMessage 보다는 HTML도 지원하는 MimeMessage 타입을 사용
            MimeMessage message = javaMailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");

            helper.setTo(targetAddress); // 메일 받는 사람 설정
            helper.setSubject(title); // 보내는 메일의 제목 설정
            helper.setText(content, true); // 보내는 메일의 내용 설정

            javaMailSender.send(message); // 메일 전송

            log.info("이메일 발송 성공 - To: {}", targetAddress);
        } catch (MessagingException e) {
            log.error("이메일 발송 실패 - To: {}, Error: {}", targetAddress, e.getMessage());
            // @Async 메서드는 별도 스레드에서 수행되므로, 예외 발생 시 호출자(Controller 등)에게 전파되지 않음.
            // 따라서 예외를 throw하는 대신, 로그를 남겨서 모니터링 가능하도록 처리
        }
    }
}
