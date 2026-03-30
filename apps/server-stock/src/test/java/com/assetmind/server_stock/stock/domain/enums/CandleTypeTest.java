package com.assetmind.server_stock.stock.domain.enums;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.stock.exception.InvalidStockParameterException;
import org.assertj.core.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

public class CandleTypeTest {
    @ParameterizedTest
    @CsvSource({
            "1m, MIN_1",
            "3m, MIN_3",
            "5m, MIN_5",
            "15m, MIN_15",
            "1d, DAY_1",
            "1w, WEEK_1",
            "1M, MONTH_1",
            "1y, YEAR_1"
    })
    @DisplayName("올바른 파라미터 문자열이 들어오면 해당하는 CandleType Enum을 반환한다.")
    void givenValidString_whenFrom_thenReturnCandleType(String input, CandleType expected) {
        // When
        CandleType actual = CandleType.from(input);

        // Then
        assertThat(actual).isEqualTo(expected);
    }

    @Test
    @DisplayName("지원하지 않는 파라미터 문자열이 들어오면 예외를 발생시킨다.")
    void givenInvalidString_whenFrom_thenThrowsException() {
        // Given
        String invalidInput = "10m"; // enum에 존재하지 않는 10분봉 요청
        String weirdInput = "1900000000000000m";

        // When & Then
        assertThatThrownBy(() -> CandleType.from(invalidInput))
                .isInstanceOf(InvalidStockParameterException.class)
                .hasMessageContaining("지원하지 않는 캔들 타입입니다");

        assertThatThrownBy(() -> CandleType.from(weirdInput))
                .isInstanceOf(InvalidStockParameterException.class);
    }

    @Test
    @DisplayName("null이 들어오면 예외를 발생시킨다.")
    void givenNull_whenFrom_thenThrowsException() {
        // When & Then
        assertThatThrownBy(() -> CandleType.from(null))
                .isInstanceOf(InvalidStockParameterException.class);
    }
}
