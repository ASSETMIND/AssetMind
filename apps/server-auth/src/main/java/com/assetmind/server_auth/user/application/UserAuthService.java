package com.assetmind.server_auth.user.application;

import com.assetmind.server_auth.global.error.ErrorCode;
import com.assetmind.server_auth.user.application.dto.TokenSetDto;
import com.assetmind.server_auth.user.application.dto.UserLoginCommand;
import com.assetmind.server_auth.user.application.port.PasswordEncoder;
import com.assetmind.server_auth.user.application.port.RefreshTokenPort;
import com.assetmind.server_auth.user.application.port.UserRepository;
import com.assetmind.server_auth.user.application.provider.AuthTokenProvider;
import com.assetmind.server_auth.user.domain.User;
import com.assetmind.server_auth.user.domain.type.UserRole;
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

    @Override
    public TokenSetDto reissueToken(String refreshToken) {
        // 토큰 유효성 검증
        authTokenProvider.validateToken(refreshToken);

        // 토큰에서 유저 정보 추출 (userId)
        UUID userId = authTokenProvider.getUserIdFromToken(refreshToken);

        String storedRefreshToken = refreshTokenPort.getRefreshToken(userId);
        // 저장소에 토큰이 없거나 요청한 토큰과 다른 토큰이라면 제거
        if (storedRefreshToken == null || !storedRefreshToken.equals(refreshToken)) {
            refreshTokenPort.delete(userId);
            throw new AuthException(ErrorCode.INVALID_TOKEN);
        }

        // role이 변경되었을 수도 있으니, 유저 정보 최신화
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new AuthException(ErrorCode.USER_NOT_FOUND));

        // 새 토큰 발급
        TokenSetDto tokenSet = authTokenProvider.createTokenSet(userId, user.getUserRole());

        // refreshToken 저장소에 다시 저장 (덮어쓰기)
        refreshTokenPort.save(userId, user.getUserRole().toString(), tokenSet.refreshTokenExpire() / 1000);

        return tokenSet;
    }
}
