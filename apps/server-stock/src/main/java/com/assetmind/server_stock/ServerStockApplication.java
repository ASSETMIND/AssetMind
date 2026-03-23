package com.assetmind.server_stock;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
public class ServerStockApplication {

	public static void main(String[] args) {
		SpringApplication.run(ServerStockApplication.class, args);
	}

}
