package com.assetmind.server_stock.stock.domain.repository;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import java.util.List;

/**
 * 주식의 실시간 체결 데이터(Raw Tick)을 영속화하고 조회하기 위한 도메인 레포지토리 인터페이스
 * 서비스 계층은 특정 데이터베이스 기술에 종속되지 않고 이 인터페이스만을 의존하여 비즈니스 로직을 수행한다.
 *
 * 단, 현재는 이 인터페이스 내부에서 Jpa Entity를 종속하고 있지만 이는 RawTick은 객체로써의 자신의 특정 비즈니스 책임이 있는게 아니라
 * 단순 DTO로써의 책임이 있다고 판단하여 굳이 도메인 내부에서 따로 객체를 만들어서 이를 종속하기 보다 우선은 JPA Entity를 종속하도록 하여
 * 개발 편의성에 더 집중했다.
 */
public interface RawTickRepository {

    /**
     * 실시간 체결 데이터를 데이터베이스에 저장
     * @param rawTickJpaEntity : 실시간 체결 데이터
     * @return 저장된 rawTickJpaEntity
     */
    RawTickJpaEntity save(RawTickJpaEntity rawTickJpaEntity);

    /**
     * 특정 종목의 가장 최근 체결 데이터를 지정된 개수만큼 조회
     * (주로 프론트엔드 상세 페이지 초기 로딩 시 차트 및 호가창 렌더링을 위해 사용)
     * @param stockCode - 종목 코드
     * @param limit - 조회할 데이터의 개수
     * @return 저장된 rawTickJpaEntity 리스트
     */
    List<RawTickJpaEntity> findRecentData(String stockCode, int limit);
}
