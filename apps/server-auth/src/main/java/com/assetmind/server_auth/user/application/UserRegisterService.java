package com.assetmind.server_auth.user.application;

import com.assetmind.server_auth.user.application.dto.UserRegisterCommand;
import com.assetmind.server_auth.user.application.port.EmailSendPort;
import com.assetmind.server_auth.user.application.port.PasswordEncoder;
import com.assetmind.server_auth.user.application.port.UserIdGenerator;
import com.assetmind.server_auth.user.application.port.UserRepository;
import com.assetmind.server_auth.user.application.port.VerificationCodeGenerator;
import com.assetmind.server_auth.user.application.port.VerificationCodePort;
import com.assetmind.server_auth.user.application.provider.SignUpTokenProvider;
import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.vo.Email;
import com.assetmind.server_auth.user.domain.vo.Password;
import com.assetmind.server_auth.user.domain.vo.UserInfo;
import com.assetmind.server_auth.user.domain.vo.Username;
import com.assetmind.server_auth.user.exception.InvalidVerificationCode;
import com.assetmind.server_auth.user.exception.UserDuplicatedEmail;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 회원가입 비즈니스 로직 Service
 * 회원가입을 위한 여러 모듈들을
 * 비즈니스 요구사항을 처리하기 위해 조합
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserRegisterService implements UserRegisterUseCase {

    // 외부 의존성 주입
    private final EmailSendPort emailSendPort;
    private final PasswordEncoder passwordEncoder;
    private final UserIdGenerator userIdGenerator;
    private final UserRepository userRepository;
    private final VerificationCodePort verificationCodePort;
    private final VerificationCodeGenerator verificationCodeGenerator;

    // 헬퍼 클래스
    private final SignUpTokenProvider signUpTokenProvider;

    // 인증 코드 유효시간 (3분)
    private static final long VERIFICATION_CODE_TTL = 180L;

    /**
     * 이메일 중복 확인
     */
    @Override
    public boolean checkEmailDuplicate(String email) {
        return userRepository.existsByEmail(email);
    }

    /**
     * 인증 코드 발송
     * 이미 가입된 이메일이면 예외 발생
     * 난수 코드 생성 -> Redis 저장 -> 이메일 발송
     * @param email
     */
    @Override
    @Transactional
    public void sendVerificationCode(String email) {
        if (userRepository.existsByEmail(email)) {
            throw new UserDuplicatedEmail();
        }

        // 인증 코드 생성
        String code = verificationCodeGenerator.generate();

        // 인증 코드 저장
        verificationCodePort.save(email, code, VERIFICATION_CODE_TTL);
        // 인증 코드 메일 발송
        emailSendPort.sendEmail(email, "인증 코드 발송", code);

        log.info(">>>[UserRegisterService] 가입 인증 코드 전송 : {}", email);
    }

    /**
     * 인증 코드 검증 및 회원 가입용 토큰 발급
     * 성공 시: Redis에서 인증 코드 삭제 후 가입용 JWT(Type: SIGN_UP) 발급
     * 실패 시: 예외 발생
     * @param email - 인증 코드를 전달한 email
     * @param code - 유저가 입력한 인증 코드
     * @return signUpToken (회원 가입용 임시 토큰)
     */
    @Override
    @Transactional
    public String verifyCode(String email, String code) {
        String savedCode = verificationCodePort.getCode(email);

        // 인증 코드가 만료되었거나(null), 일치하지 않는 경우
        if (savedCode == null || !savedCode.equals(code)) {
            throw new InvalidVerificationCode();
        }

        // 검증 성공
        verificationCodePort.remove(email);

        // 회원 가입용 토큰 발급
        return signUpTokenProvider.createToken(email);
    }

    /**
     * 최종 회원가입
     * 회원 가입용 토큰 검증 -> User 도메인 객체 생성 -> DB 저장
     * @param cmd - 회원가입 유저 데이터 DTO
     * @return 가입된 유저 ID
     */
    @Override
    @Transactional
    public UUID register(UserRegisterCommand cmd) {
        // 가입 토큰 검증 (위변조, 만료, 타입 확인) 및 이메일 추출
        String verifiedEmail = signUpTokenProvider.getEmailFromToken(cmd.signUpToken());

        // 토큰의 이메일 내용과 요청 바디의 이메일 내용이 같은지 확인
        if (!verifiedEmail.equals(cmd.email())) {
            throw new IllegalArgumentException("토큰의 이메일 정보와 입력된 이메일이 일치하지 않습니다.");
        }

        // 중복 가입 방지
        if (userRepository.existsByEmail(cmd.email())) {
            throw new UserDuplicatedEmail();
        }

        // 도메인 객체 생성
        UUID userId = userIdGenerator.generate();
        Password encodedPassword = new Password(passwordEncoder.encode(cmd.password()));
        UserInfo userInfo = new UserInfo(
                new Email(cmd.email()),
                new Username(cmd.username())
        );

        User newUser = User.createGuest(userId, userInfo, encodedPassword);

        // User 도메인 객체 저장
        User savedUser = userRepository.save(newUser);

        return savedUser.getId();
    }
}
