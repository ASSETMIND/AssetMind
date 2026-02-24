package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockMetaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface StockMetaRepository extends JpaRepository<StockMetaEntity, String> {

}
