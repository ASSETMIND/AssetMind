package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import com.assetmind.server_stock.stock.domain.repository.CandleRepository;
import jakarta.annotation.PostConstruct;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scripting.support.ResourceScriptSource;
import org.springframework.stereotype.Repository;

/**
 * 실시간 체결 데이터를 Redis(인메모리)에서 캔들(OHLCV) 형태로 집계하는 어댑터 구현체이다.
 * 해당 레포지토리는 RDB 파티션 테이블로 한번에 저장되기 전까지 트래픽을 방어하는 실시간 메모리 버퍼역할이다.
 *
 * 초당 수십~수백 건의 틱 데이터가 유입될 때 다중 스레이드의 고가/저가 갱신 과정에서
 * 발생할수 있는 경쟁 상태를 방지하기 위해, Redis 내부에서 조회/저장이 원자적으로 실행되는 Lua 스크립트를 사용한다.
 *
 * {@code candle:{type}:{stockCode}:{yyyyMMddHHmm}} 형태의 키를 사용하고,
 * 값으로는 OHLCV(Open, High, Low, Close, Volume) 필드를 가지는 Redis Hash 자료구조로 데이터를 갱신한다.
 *
 * 스케쥴러 장애시, 메모리 과부하를 방지하기 위해 최초 틱 저장시 5분의 TTL을 설정
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class CandleRedisAdapter implements CandleRepository {

    private final StringRedisTemplate redisTemplate;

    private static final String KEY_PREFIX = "candle";
    private static final DateTimeFormatter MINUTE_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmm");

    private DefaultRedisScript<Long> candleUpdateScript;

    @PostConstruct
    public void init() {
        candleUpdateScript = new DefaultRedisScript<>();
        candleUpdateScript.setScriptSource(new ResourceScriptSource(new ClassPathResource("scripts/candle_update.lua")));
        candleUpdateScript.setResultType(Long.class);
    }

    @Override
    public void save(RealTimeStockTradeEvent event, CandleType type) {
        String minuteStr = LocalDateTime.now().format(MINUTE_FORMATTER);
        String key = String.format("%s:%s:%s:%s", KEY_PREFIX, type.getValue(), event.stockCode(), minuteStr);

        redisTemplate.execute(
                candleUpdateScript,
                List.of(key), // KEYS[1]
                String.valueOf(event.currentPrice()), // ARGV[1]
                String.valueOf(event.executionVolume()) // ARGV[2]
        );
    }

    @Override
    public List<OhlcvDto> flushCandles(String targetTime, CandleType type) {
        String pattern = String.format("%s:%s:*:%s", KEY_PREFIX, type.getValue(), targetTime);
        Set<String> keys = redisTemplate.keys(pattern);

        if (keys == null || keys.isEmpty()) {
            return List.of();
        }

        List<OhlcvDto> result = new ArrayList<>();
        LocalDateTime candleTimestamp = LocalDateTime.parse(targetTime, MINUTE_FORMATTER);

        for (String key : keys) {
            Map<Object, Object> entries = redisTemplate.opsForHash().entries(key);
            if (entries.isEmpty()) continue;

            String stockCode = key.split(":")[2];

            OhlcvDto dto = new OhlcvDto(
                    stockCode,
                    candleTimestamp,
                    Double.parseDouble(entries.get("open").toString()),
                    Double.parseDouble(entries.get("high").toString()),
                    Double.parseDouble(entries.get("low").toString()),
                    Double.parseDouble(entries.get("close").toString()),
                    Long.parseLong(entries.get("volume").toString())
            );
            result.add(dto);

            redisTemplate.delete(key);
        }

        log.info("[CandleRedisAdapter] 캔들 Flush 완료, 타켓 시간: {}, 캔들 타입: {}, 처리 개수:{}", targetTime, type.getValue(), result.size());
        return result;
    }
}
