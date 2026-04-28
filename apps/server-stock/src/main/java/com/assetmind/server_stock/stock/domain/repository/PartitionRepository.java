package com.assetmind.server_stock.stock.domain.repository;

import java.time.LocalDate;

/**
 * 실시간 틱 데이터(raw_tick) 저장을 위한 파티션 테이블을 관리하는 도메인 레포지토리 인터페이스.
 * 특정 데이터베이스 기술(JPA, JDBC 등)에 종속되지 않도록 의존성을 역전(DIP)시키기 위해 사용
 * 스케줄러(Application Layer)는 이 인터페이스만 바라보고 파티션 생성을 요청
 */
public interface PartitionRepository {
    /**
     * 특정 날짜의 틱 데이터를 저장할 파티션 테이블이 존재하지 않으면 생성
     * (멱등성 보장: 이미 테이블이 존재할 경우 아무 작업도 수행하지 않음)
     *
     * @param targetDate 파티션 테이블을 생성할 대상 날짜
     */
    void createTickPartitionTable(LocalDate targetDate);
}
