package com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class KisRealTimeDataParserTest {

    private final KisRealTimeDataParser parser = new KisRealTimeDataParser();

    @Test
    @DisplayName("성공: 'H' 에러(개수 필드 누락) 시에도 1건으로 간주하여 파싱한다")
    void givenOneRecord_whenParse_thenParsing() {
        // given
        String payload = "0|H0STCNT0|005930^123000^80000^1^500^0.65^0^80000^81000^79000^0^0^100^1000^100000^0^0^0^100.0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^20^0^0^0^0^0^0^0^0^0^70000";

        // when
        List<KisRealTimeData> result = parser.parse(payload);

        // then
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().symbol()).isEqualTo("005930");
        assertThat(result.getFirst().marketStatus()).isEqualTo("20");
    }

    @Test
    @DisplayName("성공: 멀티 레코드가 포함된 데이터를 정확한 개수만큼 파싱한다")
    void givenMultiRecord_whenParse_thenParsing() {
        // given
        String record = "0^1^2^3^4^5^6^7^8^9^10^11^12^13^14^15^16^17^18^19^20^21^22^23^24^25^26^27^28^29^30^31^32^33^34^35^36^37^38^39^40^41^42^43^44^45";
        String payload = "0|H0STCNT0|2|" + record + "^" + record;

        // when
        List<KisRealTimeData> result = parser.parse(payload);

        // then
        assertThat(result).hasSize(2);
    }
}