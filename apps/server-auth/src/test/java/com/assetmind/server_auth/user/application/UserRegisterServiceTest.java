package com.assetmind.server_auth.user.application;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

import com.assetmind.server_auth.user.application.dto.UserRegisterCommand;
import com.assetmind.server_auth.user.application.port.EmailSendPort;
import com.assetmind.server_auth.user.application.port.PasswordEncoder;
import com.assetmind.server_auth.user.application.port.UserIdGenerator;
import com.assetmind.server_auth.user.application.port.UserRepository;
import com.assetmind.server_auth.user.application.port.VerificationCodeGenerator;
import com.assetmind.server_auth.user.application.port.VerificationCodePort;
import com.assetmind.server_auth.user.application.provider.SignUpTokenProvider;
import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.type.UserRole;
import com.assetmind.server_auth.user.domain.vo.Email;
import com.assetmind.server_auth.user.domain.vo.Password;
import com.assetmind.server_auth.user.domain.vo.UserInfo;
import com.assetmind.server_auth.user.domain.vo.Username;
import com.assetmind.server_auth.user.exception.InvalidVerificationCode;
import com.assetmind.server_auth.user.exception.UserDuplicatedEmail;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * UserRegisterService 단위 테스트
 * 이메일 중복 확인 로직 확인
 * 가입 인증 코드 전송 로직 확인
 * 인증 번호 검증 및 토큰 발급 로직 확인
 * 회원가입 성공 시 유저 도메인 객체 저장 로직 확인
 */
@ExtendWith(MockitoExtension.class)
class UserRegisterServiceTest {

    @InjectMocks
    private UserRegisterService userRegisterService;

    // 외부 협력 객체들 Mocking
    @Mock private EmailSendPort emailSendPort;
    @Mock private PasswordEncoder passwordEncoder;
    @Mock private UserIdGenerator userIdGenerator;
    @Mock private UserRepository userRepository;
    @Mock private VerificationCodeGenerator verificationCodeGenerator;
    @Mock private VerificationCodePort verificationCodePort;
    @Mock private SignUpTokenProvider signUpTokenProvider;

    private final UserInfo userInfo = new UserInfo(
            new Email("test@test.com"),
            new Username("테스트001")
    );
    private final String token = "valid-jwt";

    @Test
    @DisplayName("성공: 중복된 이메일이 아니면 false를 응답한다.")
    void givenValidEmail_whenCheckEmailDuplicate_thenReturnFalse() {
        // given
        // 중복되지 않은 이메일이 들어왔다고 가정
        String validEmail = userInfo.email().value();
        given(userRepository.existsByEmail(userInfo.email().value())).willReturn(false);

        // when
        boolean result = userRegisterService.checkEmailDuplicate(validEmail);

        // then
        assertThat(result).isFalse();
    }

    @Test
    @DisplayName("실패: 중복된 이메일이 이면 true를 응답한다.")
    void givenDuplicatedEmail_whenCheckEmailDuplicate_thenReturnTrue() {
        // given
        // 중복된 이메일이 들어왔다고 가정
        String duplicatedEmail = "valid@test.com";
        given(userRepository.existsByEmail(duplicatedEmail)).willReturn(true);

        // when
        boolean result = userRegisterService.checkEmailDuplicate(duplicatedEmail);

        // then
        assertThat(result).isTrue();
    }

    @Test
    @DisplayName("성공: 중복된 이메일이 아니면 인증 코드 생성 후 저장하고 메일을 보낸다.")
    void givenValidEmail_whenSendVerification_thenSaveAndSendEmail() {
        // given
        String validEmail = userInfo.email().value();
        String code = "123456";
        given(userRepository.existsByEmail(validEmail)).willReturn(false);
        given(verificationCodeGenerator.generate()).willReturn(code);

        // when
        userRegisterService.sendVerificationCode(validEmail);

        // then
        // Redis 저장 메서드가 잘 실행되었는지 확인
        verify(verificationCodePort).save(eq(validEmail), eq(code), eq(180L));
        // 메일 발송 메서드가 잘 실행되었는지 확인
        verify(emailSendPort).sendEmail(eq(validEmail), eq("인증 코드 발송"), eq(code));
    }

    @Test
    @DisplayName("실패: 중복된 이메일이 이면 예외(UserDuplicatedEmail)를 던진다.")
    void givenDuplicatedEmail_whenSendVerification_thenThrowException() {
        // given
        String duplicatedEmail = "valid@test.com";
        given(userRepository.existsByEmail(duplicatedEmail)).willReturn(true);

        // when & then
        assertThatThrownBy(() -> userRegisterService.sendVerificationCode(duplicatedEmail))
                .isInstanceOf(UserDuplicatedEmail.class)
                .hasMessageContaining("중복된 이메일입니다.");
    }


    @Test
    @DisplayName("성공: 유효한 인증 코드인 경우, 저장소에서 인증 코드를 삭제하고 회원가입용 토큰을 발급한다.")
    void givenValidCode_whenVerifyCode_thenRemoveCodeAndIssueRegisterCode() {
        // given
        String validEmail = userInfo.email().value();
        String mockSavedCode = "123456";
        given(verificationCodePort.getCode(validEmail)).willReturn(mockSavedCode);
        given(signUpTokenProvider.createToken(validEmail)).willReturn(token);

        // when
        String result = userRegisterService.verifyCode(validEmail, mockSavedCode);

        // then
        assertThat(result).isEqualTo(token);
        verify(verificationCodePort).remove(eq(validEmail));
    }

    @Test
    @DisplayName("실패: 유효하지 않은 인증 코드인 경우, 예외(InvalidVerificationCode)를 던진다.")
    void givenInvalidCode_whenVerifyCode_thenThrowException() {
        // given
        String validEmail = userInfo.email().value();
        String validCode = "123456";
        given(verificationCodePort.getCode(validEmail)).willReturn("999999");

        // when & then
        assertThatThrownBy(() -> userRegisterService.verifyCode(validEmail, validCode))
                .isInstanceOf(InvalidVerificationCode.class)
                .hasMessageContaining("유효하지 않은 인증 코드입니다.");

        // 틀린 인증번호로 접근했으니 원래있던 인증번호는 삭제되면 안됨
        verify(verificationCodePort, never()).remove(any());
    }

    @Test
    @DisplayName("성공: 올바른 UserRegisterCommand 라면, 회원가입에 성공하고 유저를 저장한다.")
    void givenUserRegisterCommand_whenRegister_thenSaveUserAndReturnUserUUID() {
        // given
        UserRegisterCommand cmd = new UserRegisterCommand(
                userInfo.email().value(),
                "test1234",
                userInfo.username().value(),
                token
        );
        UUID mockUserId = UUID.randomUUID();

        User mockUser = User.withId(mockUserId, userInfo, new Password("test1234"), null,
                UserRole.GUEST);

        given(signUpTokenProvider.getEmailFromToken(cmd.signUpToken())).willReturn(userInfo.email().value());
        given(userRepository.existsByEmail(cmd.email())).willReturn(false);
        given(userIdGenerator.generate()).willReturn(mockUserId);
        given(passwordEncoder.encode(cmd.password())).willReturn("encoded_pw");

        given(userRepository.save(any(User.class))).willReturn(mockUser);

        // when
        UUID result = userRegisterService.register(cmd);

        // then
        assertThat(result).isEqualTo(mockUserId);
        verify(userRepository).save(any(User.class));
        verify(passwordEncoder).encode(eq(cmd.password()));
    }

    @Test
    @DisplayName("실패: 토큰의 이메일과 요청 이메일이 다르면, 예외(IllegalArgumentException)을 던진다.")
    void givenInvalidEmailInToken_whenRegister_thenThrowException() {
        // given
        UserRegisterCommand cmd = new UserRegisterCommand(
                userInfo.email().value(),
                "test1234",
                userInfo.username().value(),
                token
        );
        String invalidEmail = "invalid@test.com";

        // 토큰에는 invalid@test.com 이지만 요청은 test@test.com인 상황
        given(signUpTokenProvider.getEmailFromToken(cmd.signUpToken())).willReturn(invalidEmail);

        // when & then
        assertThatThrownBy(() -> userRegisterService.register(cmd))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("토큰의 이메일 정보와 입력된 이메일이 일치하지 않습니다.");

        verify(userRepository, never()).save(any());
    }

    @Test
    @DisplayName("실패: 중복된 이메일이라면, 예외(UserDuplicatedEmail)를 던진다.")
    void givenDuplicatedEmail_whenRegister_thenThrowException() {
        // given
        UserRegisterCommand cmd = new UserRegisterCommand(
                userInfo.email().value(),
                "test1234",
                userInfo.username().value(),
                token
        );
        given(signUpTokenProvider.getEmailFromToken(cmd.signUpToken())).willReturn(cmd.email());
        given(userRepository.existsByEmail(cmd.email())).willReturn(true);

        // when & then
        assertThatThrownBy(() -> userRegisterService.register(cmd))
                .isInstanceOf(UserDuplicatedEmail.class)
                .hasMessageContaining("중복된 이메일입니다.");
    }
}