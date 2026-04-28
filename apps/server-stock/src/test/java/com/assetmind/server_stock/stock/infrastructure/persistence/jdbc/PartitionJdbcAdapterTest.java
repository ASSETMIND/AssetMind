package com.assetmind.server_stock.stock.infrastructure.persistence.jdbc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import java.time.LocalDate;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;

@ExtendWith(MockitoExtension.class)
class PartitionJdbcAdapterTest {

    @Mock
    private JdbcTemplate jdbcTemplate;

    @InjectMocks
    private PartitionJdbcAdapter partitionJdbcAdapter;

    @Test
    @DisplayName("특정 날짜가 주어지면, 해당 날짜에 맞는 파티션 생성 DDL 쿼리를 정확히 생성하여 실행한다.")
    void givenDate_whenCreateTickPartitionTable_thenExecutesCorrectSql() {
        // Given: 2026년 3월 31일이라는 타겟 날짜 설정
        LocalDate targetDate = LocalDate.of(2026, 3, 31);

        // When: 어댑터 메서드 호출
        partitionJdbcAdapter.createTickPartitionTable(targetDate);

        // Then: JdbcTemplate의 execute() 메서드가 호출될 때 전달된 SQL 문자열을 낚아챔
        ArgumentCaptor<String> sqlCaptor = ArgumentCaptor.forClass(String.class);
        verify(jdbcTemplate, times(1)).execute(sqlCaptor.capture());

        String executedSql = sqlCaptor.getValue();

        // 생성된 쿼리가 의도한 DDL과 완벽히 일치하는지 검증
        assertThat(executedSql).contains("CREATE TABLE IF NOT EXISTS raw_tick_20260331");
        assertThat(executedSql).contains("PARTITION OF raw_tick");
        assertThat(executedSql).contains("FOR VALUES FROM ('2026-03-31 00:00:00') TO ('2026-04-01 00:00:00')");
    }

    @Test
    @DisplayName("DB 쿼리 실행 중 에러가 발생하더라도, 예외를 삼키고(catch) 스케줄러를 중단시키지 않는다.")
    void givenDbException_whenCreateTickPartitionTable_thenCatchesExceptionAndDoesNotThrow() {
        // Given: DB에 일시적인 장애가 발생했다고 가정
        LocalDate targetDate = LocalDate.of(2026, 3, 31);

        // jdbcTemplate이 어떤 SQL을 받든 무조건 DB 에러(DataAccessException)를 뱉도록 Mocking
        doThrow(new org.springframework.dao.DataAccessResourceFailureException("임의의 DB 연결 실패 에러"))
                .when(jdbcTemplate).execute(anyString());

        // When & Then: 어댑터 메서드를 호출했을 때, 밖으로 에러가 터져 나오지 않는지 검증
        assertDoesNotThrow(() -> {
            partitionJdbcAdapter.createTickPartitionTable(targetDate);
        });

        // 실제로 execute()가 1번 호출되긴 했는지 검증 (예외가 발생했어도 시도는 했어야 함)
        verify(jdbcTemplate, times(1)).execute(anyString());
        }
}