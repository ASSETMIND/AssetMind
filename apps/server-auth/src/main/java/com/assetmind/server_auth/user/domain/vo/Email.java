package com.assetmind.server_auth.user.domain.vo;

/**
 * User의 이메일 VO 객체
 * @param value - 서비스에 사용될 유저 이메일 값
 */
public record Email(
        String value
) {

    /**
     * email의 값 유효성 검증
     * @param value
     */
    public Email {
        if(value == null || !checkValidation(value)) {
            throw new IllegalArgumentException("유효하지 않은 이메일 형식입니다.");
        }
    }

    /**
     * 이메일의 정규 형식 검사
     * [\w-\.]+ : 영어, 숫자, 언더바, 하이픈(-), 점(.)으로 이루어진 문자가 1가지 이상 존재 그리고 해당 문자 덩어리가 반복 가능 (이메일 아이디 부분)
     * @ : 반드시 필요
     * ([\w-]+\.)+ : 영어, 숫자, 언더바, 하이픈이 포함된 덩어리에 점이 추가된 덩어리가 반복 가능 (도메인 부분, 예) wotjr.co.)
     * [/w-]{2,} : 영어, 숫자, 언더바, 하이픈으로 이루어졌으면서 2글자 이상 문자 (도메인의 마지막 부분, 예) kr)
     */
    private boolean checkValidation(String value) {
        return value.matches("^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,}$");
    }

}
