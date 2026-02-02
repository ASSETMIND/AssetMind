package com.assetmind.server_auth;

import com.assetmind.server_auth.global.config.JwtProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(JwtProperties.class)
public class ServerAuthApplication {

	public static void main(String[] args) {
		SpringApplication.run(ServerAuthApplication.class, args);
	}

}
