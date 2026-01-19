package com.assetmind.server_auth.user.infrastructure.mail;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.then;

import jakarta.mail.MessagingException;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
import java.util.Properties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.BDDMockito;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mail.javamail.JavaMailSender;

/**
 * Email Sender Adapter 단위 테스트
 */
@ExtendWith(MockitoExtension.class)
class EmailSenderAdapterTest {

    @Mock
    private JavaMailSender javaMailSender;

    @InjectMocks
    private EmailSenderAdapter emailSenderAdapter;

    /**
     * MimeMessage에 존재하는 Content 내용을 검증하기 위해서는 MultiPart의 Body를 분해야하는데
     * 이를 위한 헬퍼 메서드를 구현하기에는 테스트의 복잡도가 더 늘어날 것 같아서 제목과 수신자의 검증만 하고
     * 추후 통합 테스트에서 내용을 검증하는 식으로 작성하겠습니다.
     */
    @Test
    @DisplayName("성공: 이메일 발송 메서드를 수행하면, 수신자와 제목이 정확해야함")
    void givenMailMessage_whenSendEmail_thenCorrectMailMessage() throws MessagingException {
        // given
        String targetAddress = "test@test.com";
        String title = "테스트 제목";
        String content = "<h1>테스트 내용</h1>";

        MimeMessage mimeMessage = new MimeMessage(Session.getDefaultInstance(new Properties()));
        BDDMockito.given(javaMailSender.createMimeMessage()).willReturn(mimeMessage);

        // when
        emailSenderAdapter.sendEmail(targetAddress, title, content);

        // then
        // ArgumentCaptor로 send() 메서드에 넘어간 이메일 메타데이터를 낚아챔
        ArgumentCaptor<MimeMessage> messageCaptor = ArgumentCaptor.forClass(MimeMessage.class);
        then(javaMailSender).should().send(messageCaptor.capture());

        MimeMessage capturedMessage = messageCaptor.getValue();

        // 이메일 메타 데이터 내용 검증
        assertThat(capturedMessage.getSubject()).isEqualTo(title);
        assertThat(capturedMessage.getAllRecipients()[0].toString()).isEqualTo(targetAddress);
    }

    @Test
    @DisplayName("실패: 메일 전송 중 에러가 발생해도 예외가 전파되지 않고(로그 처리) 안전하게 종료되어야 한다.")
    void givenMailMessage_whenSendEmail_thenDoesNotThrowException() {
        // given
        String targetAddress = "test@test.com";
        String title = "테스트 제목";
        String content = "<h1>테스트 내용</h1>";

        MimeMessage mimeMessage = new MimeMessage(Session.getDefaultInstance(new Properties()));
        BDDMockito.given(javaMailSender.createMimeMessage()).willReturn(mimeMessage);

        // send()가 호출되면 에러를 던지도록 설정 (Unhappy Case 연출)
        BDDMockito.willThrow(new org.springframework.mail.MailSendException("SMTP 서버 연결 실패"))
                .given(javaMailSender).send(any(MimeMessage.class));

        // when & then
        // 에러가 발생해도 Adapter 내부의 try-catch가 먹어주기 때문에
        // 외부로는 에러가 튀어나오지 않아야 한다(.doesNotThrowAnyException)
        assertThatCode(() -> emailSenderAdapter.sendEmail(targetAddress, title, content))
                .doesNotThrowAnyException();
    }
}