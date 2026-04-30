package com.assetmind.server_stock.stock.application.scheduler;

import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.assetmind.server_stock.stock.domain.repository.PartitionRepository;
import java.time.LocalDate;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class PartitionCreationSchedulerTest {

    @Mock
    private PartitionRepository partitionRepository;

    @InjectMocks
    private PartitionCreationScheduler partitionCreationScheduler;

    @Test
    @DisplayName("서버 기동 완료 시(ApplicationReady), 오늘과 내일의 파티션 생성을 각각 1번씩 호출한다.")
    void givenApplicationReady_whenInitPartitions_thenCreatesTodayAndTomorrow() {
        // Given
        LocalDate today = LocalDate.now();
        LocalDate tomorrow = today.plusDays(1);

        // When
        partitionCreationScheduler.initPartitionsOnReady();

        // Then
        verify(partitionRepository, times(1)).createTickPartitionTable(today);
        verify(partitionRepository, times(1)).createTickPartitionTable(tomorrow);
    }

    @Test
    @DisplayName("매일 밤 11시 정기 스케줄러 가동 시, 내일 날짜의 파티션 생성을 1번 호출한다.")
    void givenScheduledTime_whenScheduleCreation_thenCreatesTomorrow() {
        // Given
        LocalDate tomorrow = LocalDate.now().plusDays(1);

        // When
        partitionCreationScheduler.scheduleCreationNextDayPartition();

        // Then
        verify(partitionRepository, times(1)).createTickPartitionTable(tomorrow);
    }
}