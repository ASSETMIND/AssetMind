package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * KIS 국내주식 실시간체결가 (KRX) 웹소켓 구독 요청 DTO
 * @param header 인증정보
 * @param body 종목정보
 */
public record KisSubscriptionRequest(
        @JsonProperty("header") Header header,
        @JsonProperty("body") Body body

) {

    /**
     * 웹소켓 구독 요청의 Header(인증정보)
     * @param approvalKey 실시간 (웹소켓) 접속키 발급 API(/oauth2/Approval)를 사용하여 발급받은 웹소켓 접속키
     * @param custType B: 법인 | P: 개인 (default)
     * @param trType 1: 등록 | 2: 해제
     * @param contentType utf-8
     */
    public record Header(
            @JsonProperty("approval_key") String approvalKey,
            @JsonProperty("custtype") String custType,
            @JsonProperty("tr_type") String trType,
            @JsonProperty("content-type") String contentType
    ) {}

    /**
     * 웹소켓 구독 요청의 Body(종목정보)
     * KIS 요청 JSON 포맷에 맞게 body 안에 input key를 넣어야함
     * @param input
     */
    public record Body(
            @JsonProperty("input") Input input
    ) {}


    /**
     * Body의 실제 내용
     * @param trId H0STCNT0 : 실시간 주식 체결가
     * @param trKey 종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
     */
    public record Input(
            @JsonProperty("tr_id") String trId,
            @JsonProperty("tr_key") String trKey
    ) {}

    // 사용 편의를 위한 팩토리 메서드
    public static KisSubscriptionRequest of(String approvalKey, String stockCode) {
        return new KisSubscriptionRequest(
                new Header(approvalKey, "P", "1", "utf-8"),
                new Body(new Input("H0STCNT0", stockCode))
        );
    }
}
