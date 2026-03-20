package com.assetmind.server_stock.global.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.repository.configuration.EnableRedisRepositories;

@Configuration
@EnableRedisRepositories(basePackages = "com.assetmind.server_stock.stock.infrastructure.persistence.redis")
public class RedisConfig {

}
