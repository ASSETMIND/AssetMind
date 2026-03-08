-- 테스트를 위한 KOSPI / KOSDAQ 주요 종목 메타데이터 초기화
-- (실제 운영 환경에서는 KRX API나 배치 잡을 통해 최신화 필요)

INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('005930', '삼성전자', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('000660', 'SK하이닉스', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('373220', 'LG에너지솔루션', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('207940', '삼성바이오로직스', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('005380', '현대차', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('000270', '기아', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('068270', '셀트리온', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('035420', 'NAVER', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('035720', '카카오', 'KOSPI');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('086520', '에코프로', 'KOSDAQ');
INSERT INTO stock_meta_data (stock_code, stock_name, market) VALUES ('247540', '에코프로비엠', 'KOSDAQ');

-- 주의: 테이블 이름(stock_meta)과 컬럼명은 실제 엔티티(@Table, @Column) 설정에 맞게 수정해주세요!