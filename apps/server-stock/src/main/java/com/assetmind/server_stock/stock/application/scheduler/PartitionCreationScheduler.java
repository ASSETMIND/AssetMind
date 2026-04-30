package com.assetmind.server_stock.stock.application.scheduler;

import com.assetmind.server_stock.stock.domain.repository.PartitionRepository;
import java.time.LocalDate;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 실시간 체결 데이터(raw_tick) 파티션 테이블 생성을 자동화 하는 스케줄러
 * 해당 날짜의 파티션 테이블이 존재하지 않으면 DB에서 "no partition of relation" 에러가 발생하는 것을 방지하기 위해
 * 서버 실행 시 또는 자정 전에 필요한 날짜의 파티션 테이블을 미리 준비한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PartitionCreationScheduler {

    private final PartitionRepository partitionRepository;

    /**
     * 스프링 컨텍스트가 모두 로드되고 서버의 준비가 끝난 후에
     * DB 파티션 생성 쿼리를 실행
     */
    @EventListener(ApplicationReadyEvent.class)
    public void initPartitionsOnReady() {
        partitionRepository.createTickPartitionTable(LocalDate.now());
        partitionRepository.createTickPartitionTable(LocalDate.now().plusDays(1));
    }

    @Scheduled(cron = "0 0 23 * * *")
    public void scheduleCreationNextDayPartition() {
        LocalDate tomorrow = LocalDate.now().plusDays(1);
        partitionRepository.createTickPartitionTable(tomorrow);
    }

}
