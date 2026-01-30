package com.assetmind.server_auth.user.application;

import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.application.dto.UserLoginCommand;
import com.assetmind.server_auth.user.application.port.PasswordEncoder;
import com.assetmind.server_auth.user.application.port.RefreshTokenPort;
import com.assetmind.server_auth.user.application.port.UserRepository;
import com.assetmind.server_auth.user.application.provider.AuthTokenProvider;
import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.exception.AuthException;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 로그인/로그아웃을 비롯한 여러 Auth 관련 비즈니스 로직 Service
 * 유저 인증을 위한 여러 모듈들을
 * 비즈니스 요구사항을 처리하기 위해 조합
 */
@Service
@RequiredArgsConstructor
public class UserAuthService implements UserAuthUseCase {

    private final UserRepository userRepository;
    private final RefreshTokenPort refreshTokenPort;
    private final AuthTokenProvider authTokenProvider;
    private final PasswordEncoder passwordEncoder;

    @Override
    @Transactional
    public TokenSetDto login(UserLoginCommand cmd) {
        // 유저 조회
        User user = userRepository.findByEmail(cmd.email())
                .orElseThrow(() -> new AuthException(ErrorCode.USER_NOT_FOUND));

        // 비밀번호 검증
        if (!passwordEncoder.matches(cmd.password(), user.getPasswordValue())) {
            throw new AuthException(ErrorCode.INCORRECT_PASSWORD);
        }

        // ps. 유저가 토큰을 발급 받고 나서, 소셜인증을 통해 "USER" Role이 되었다면 로그인 재시도를 하도록 추후에 계획
        TokenSetDto tokenSet = authTokenProvider.createTokenSet(user.getId(), user.getUserRole()); // 토큰 발급

        // Redis에 RefreshToken 저장
        refreshTokenPort.save(user.getId(), tokenSet.refreshToken(), tokenSet.refreshTokenExpire() / 1000);

        return tokenSet;
    }

    @Override
    @Transactional
    public void logout(UUID userId) {
        refreshTokenPort.delete(userId);
    }
}
