package com.assetmind.server_stock.stock.infrastructure.persistence.jdbc;

import com.assetmind.server_stock.stock.domain.repository.PartitionRepository;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/**
 * {@link PartitionRepository} 인터페이스를 Spring JDBC 기술로 구현한 어댑터.
 * PostgreSQL의 고유 기능인 테이블 파티셔닝(Range Partition) DDL을 동적으로 실행하기 위해
 * JPA(Hibernate) 대신 Native Query 전송에 유리한 JdbcTemplate을 사용
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class PartitionJdbcAdapter implements PartitionRepository {

    private final JdbcTemplate jdbcTemplate;

    @Override
    public void createTickPartitionTable(LocalDate targetDate) {
        // 파티션 테이블의 기간(Range) 설정
        LocalDate nextDate = targetDate.plusDays(1);

        // 파티션 테이블명 생성 (raw_tick_{yyyyMMdd}, 예: raw_tick_20260331)
        String partitionSuffix = targetDate.format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        String tableName = "raw_tick_" + partitionSuffix;

        // PostgreSQL 전용 파티션 생성 Native Query
        String sql = String.format(
                "CREATE TABLE IF NOT EXISTS %s PARTITION OF raw_tick "
                        + "FOR VALUES FROM ('%s 00:00:00') TO ('%s 00:00:00')",
                tableName, targetDate, nextDate
        );

        try {
            jdbcTemplate.execute(sql);
            log.info("[PartitionJdbcAdapter] 파티션 테이블 생성 완료: {}", tableName);
        } catch (Exception e) {
            log.error("[PartitionJdbcAdapter] 파티션 테이블 생성 중 오류 발생 {}", tableName, e);
        }
    }
}
