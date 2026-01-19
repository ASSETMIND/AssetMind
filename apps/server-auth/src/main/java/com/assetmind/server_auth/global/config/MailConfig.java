package com.assetmind.server_auth.global.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * Mail 관련 설정
 * 메일 발송은 네트워크를 통해 진행되기 때문에 네트워크 상황에 따라 n초 이상이 걸림
 * 따라서 비동기적인 처리가 필요함
 */
@Configuration
@EnableAsync // 비동기 처리 활성화
public class MailConfig {
    /**
     * JavaMailSender는 yml의 설정만으로 자동 등록되므로 Bean 설정 생략 가능
     */
}
