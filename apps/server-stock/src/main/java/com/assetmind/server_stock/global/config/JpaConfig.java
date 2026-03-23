package com.assetmind.server_stock.global.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@Configuration
@EnableJpaRepositories(basePackages = "com.assetmind.server_stock.stock.infrastructure.persistence.jpa")
public class JpaConfig {

}
