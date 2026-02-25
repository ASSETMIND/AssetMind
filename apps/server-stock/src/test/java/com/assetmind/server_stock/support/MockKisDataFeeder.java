package com.assetmind.server_stock.support;

/**
 * 테스트를 위해 KIS 실시간 주가 데이터 응답 포맷을 모방하여
 * 실시간 주가 데이터를 주는 역할을 함
 */
public class MockKisDataFeeder {

    // 46개의 필드를 가진 배열을 생성하여 KIS 규격과 동일하게 맞춤
    private static String generateBaseDataPart(String stockCode, String currentPrice) {
        String[] fields = new String[46];

        // 빈 배열을 빈 문자열로 초기화 (null 방지)
        for (int i = 0; i < 46; i++) {
            fields[i] = "";
        }

        // 파서(KisRealTimeDataParser)가 매핑하는 필수 인덱스 위치에 값 주입
        fields[0] = stockCode;           // 종목코드
        fields[1] = "120000";            // 체결시간 (12:00:00)
        fields[2] = currentPrice;        // 현재가
        fields[3] = "2";                 // 전일대비부호 (상승)
        fields[4] = "1000";              // 전일대비
        fields[5] = "1.35";              // 전일대비율
        fields[7] = "74000";             // 시가
        fields[8] = "76000";             // 고가
        fields[9] = "73000";             // 저가
        fields[12] = "500";              // 체결거래량
        fields[13] = "1500000";          // 누적거래량
        fields[14] = "112500000000";     // 누적거래대금
        fields[18] = "150.5";            // 체결강도
        fields[34] = "1";                // 장운영구분 (정규장)

        return String.join("^", fields);
    }

    /**
     * 정상 다건/단건 데이터 생성 (예: 001, 004)
     */
    public static String createMockDataWithCount(String stockCode, String currentPrice, int count) {
        StringBuilder dataPartBuilder = new StringBuilder();

        for (int i = 0; i < count; i++) {
            if (i > 0) dataPartBuilder.append("^"); // 다건일 경우 ^ 로 이어붙임

            // 다건일 경우 가격이 변하는 것처럼 보이게 100원씩 더함
            String price = String.valueOf(Long.parseLong(currentPrice) + (i * 100));
            dataPartBuilder.append(generateBaseDataPart(stockCode, price));
        }

        String countStr = String.format("%03d", count); // 001, 002 포맷
        return "0|H0STCNT0|" + countStr + "|" + dataPartBuilder.toString();
    }

    /**
     * 건수가 생략된 엣지 케이스 데이터 생성
     */
    public static String createMockDataWithoutCount(String stockCode, String currentPrice) {
        String dataPart = generateBaseDataPart(stockCode, currentPrice);

        // 건수 필드 없이 데이터가 바로 옴
        return "0|H0STCNT0|" + dataPart;
    }
}
