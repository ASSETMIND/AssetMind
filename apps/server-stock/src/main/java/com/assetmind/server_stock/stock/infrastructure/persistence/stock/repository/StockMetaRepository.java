package com.assetmind.server_stock.stock.infrastructure.persistence.stock.repository;

import com.assetmind.server_stock.stock.infrastructure.persistence.stock.entity.StockMetaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface StockMetaRepository extends JpaRepository<StockMetaEntity, String> {

}
