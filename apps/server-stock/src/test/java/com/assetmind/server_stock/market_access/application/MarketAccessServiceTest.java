package com.assetmind.server_stock.market_access.application;

import static org.assertj.core.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.BDDMockito.*;

import com.assetmind.server_stock.market_access.domain.ApiAccessToken;
import com.assetmind.server_stock.market_access.domain.MarketTokenProvider;
import com.assetmind.server_stock.market_access.domain.exception.MarketAccessFailedException;
import org.assertj.core.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.BDDMockito;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class MarketAccessServiceTest {

    @Mock
    private MarketTokenProvider marketTokenProvider;

    @InjectMocks
    private MarketAccessService marketAccessService;

    @Test
    @DisplayName("애플리케이션 Init 시에 토큰을 발급받아 캐싱한다.")
    void givenStartApplication_whenInit_thenCachedToken() {
        // given
        // 예상 토큰 준비: Mock TokenProvider가 호출되면 해당 객체를 리턴하도록 설정
        String expectedToken = "valid-test-token";
        when(marketTokenProvider.fetchToken()).thenReturn(ApiAccessToken.createApiAccessToken(expectedToken, 21600000));

        // when
        marketAccessService.init();

        // then
        verify(marketTokenProvider, times(1)).fetchToken(); // 실제로 Provider의 fetchToken이 1번 호출되었는지 검증

        assertThat(marketAccessService.getAccessToken()).isEqualTo(expectedToken); // 캐싱된 토큰이 설정한 Mock Token 값과 같은지 검증
    }

    @Test
    @DisplayName("캐싱된 토큰이 있으면 Provider를 호출하지 않고 캐싱되어 있는 값을 반환한다.")
    void givenAlreadyHaveCachedToken_whenGetAccessToken_thenReturnCachedToken() {
        // given
        // 예상 캐싱 토큰 준비: Mock TokenProvider가 호출되면 해당 객체를 리턴하도록 설정
        String cachedToken = "cached-token";
        when(marketTokenProvider.fetchToken()).thenReturn(ApiAccessToken.createApiAccessToken(cachedToken, 21600000));

        marketAccessService.init(); // 예상 토큰 미리 캐싱

        // when
        String token1 = marketAccessService.getAccessToken();
        String token2 = marketAccessService.getAccessToken();

        // then
        // 두 번 호출 된 값이 캐싱된 토큰과 같은지 확인하여 캐싱된 토큰이 있으면 캐싱되어 있는 값을 반환하는지 검증
        assertThat(token1).isEqualTo(cachedToken);
        assertThat(token2).isEqualTo(cachedToken);

        // init()에서 1번 호출된 것 외에 추가로 호출하지 않는지 검증
        verify(marketTokenProvider, times(1)).fetchToken();
    }

    @Test
    @DisplayName("캐싱된 토큰이 없으면 Provider를 호출하여 새 토큰을 캐싱하고 해당 토큰을 반환한다.")
    void givenNotHaveCachedToken_whenGetAccessToken_thenReturnNewToken() {
        // given
        // init()을 호출하지 않아서 캐싱된 토큰이 존재하지 않는 상태
        String newToken = "new-token";
        when(marketTokenProvider.fetchToken()).thenReturn(ApiAccessToken.createApiAccessToken(newToken, 21600000));

        // when
        String token = marketAccessService.getAccessToken();
        String cachedToken = marketAccessService.getAccessToken();

        // then
        assertThat(token).isEqualTo(newToken);
        assertThat(cachedToken).isEqualTo(newToken); // 캐싱된 새 토큰이 반환됐는지 검증

        verify(marketTokenProvider, times(1)).fetchToken();
    }

    @Test
    @DisplayName("스케줄러에 의해 토큰 캥신 시 토큰 값이 업데이트된다.")
    void givenValidOldToken_whenScheduleTokenRefresh_thenUpdateToken() {
        // given
        // 첫 번째 호출(init)과 두 번째 호출(refresh)의 반환값을 다르게 설정하여 다른 토큰이라는 것을 표현
        when(marketTokenProvider.fetchToken())
                .thenReturn(ApiAccessToken.createApiAccessToken("old-token", 21600000))
                .thenReturn(ApiAccessToken.createApiAccessToken("new-token", 21600000));

        marketAccessService.init(); // 현재 상태: old-token

        // when
        marketAccessService.scheduleTokenRefresh(); // 스케줄러 강제 실행

        // then
        String token = marketAccessService.getAccessToken();
        assertThat(token).isEqualTo("new-token");
        verify(marketTokenProvider, times(2)).fetchToken();
    }

    @Test
    @DisplayName("토큰 갱신 중 에러가 발생하면 기존 토큰을 유지한다.")
    void givenValidOldToken_whenRefreshAccessTokenFail_thenKeepValidOldToken() {
        // given
        when(marketTokenProvider.fetchToken())
                .thenReturn(ApiAccessToken.createApiAccessToken("valid-old-token", 21600000))
                .thenThrow(new MarketAccessFailedException("KIS API Error"));

        marketAccessService.init(); // 토큰 최초 발급 성공

        // when
        // 토큰 갱신 시도 -> 내부에서 예외 발생 -> catch
        marketAccessService.scheduleTokenRefresh();

        // then
        String token = marketAccessService.getAccessToken();
        assertThat(token).isEqualTo("valid-old-token"); // 갱신 과정에서 예외가 났으므로 new-token 으로 바뀌지 않아야함
    }
}