import csv
import random
from datetime import datetime, timedelta


def generate_candles(filename="load_test_1m_candles.csv", total_rows=10_000_000):
    # 부하 테스트시 진행할 타켓 6개의 주식 종목
    target_stock_codes = ['005930', '000660', '035420', '035720', '005380', '000270']

    # DB를 무겁게 만드는 더미 종목 74개의 종목
    dummy_stock_codes = [f"DUMMY_{i:03d}" for i in range(1, 80 - len(target_stock_codes) + 1)]

    all_stock_codes = target_stock_codes + dummy_stock_codes
    num_stocks = len(all_stock_codes)

    start_time = datetime(2023, 1, 1, 9, 0)

    # 각 종목별 이전 종가를 기억하는 딕셔너리 (초기 가격 1만 ~ 20만)
    last_closes = {stock_code: random.randint(10000, 200000) for stock_code in all_stock_codes}

    # 실제 캔들 처럼 유의미한 변동성 제공
    volatility = 0.002  # 1분당 변동성 (0.2% 내외)
    drift = 0.00005  # 아주 미세안 우상향 추세

    print(f"{total_rows:,} 건의 캔들 데이터 생성 시작...")

    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["stock_code", "candle_timestamp", "open_price", "high_price",
                         "low_price", "close_price", "volume"])

        current_time = start_time

        for i in range(total_rows):
            stock_code = all_stock_codes[i % num_stocks]
            open_price = last_closes[stock_code]

            change_pct = drift + random.gauss(0, volatility)
            close_price = int(open_price * (1 + change_pct))

            if close_price < 500: close_price = 500

            max_oc = max(open_price, close_price)
            min_oc = min(open_price, close_price)
            high_price = int(max_oc * (1 + abs(random.gauss(0, volatility * 0.5))))
            low_price = int(min_oc * (1 - abs(random.gauss(0, volatility * 0.5))))

            volume = int(abs(random.gauss(5000, 2000)) + random.randint(100, 500))
            if random.random() < 0.01:
                volume *= random.randint(5, 15)

            last_closes[stock_code] = close_price

            writer.writerow([
                stock_code,
                current_time.strftime("%Y-%m-%d %H:%M:00"),
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            ])

            # 80개의 종목을 다 돌았으면 1분 증가
            if i % num_stocks == num_stocks - 1:
                current_time += timedelta(minutes=1)

            if (i + 1) % 1_000_000 == 0:
                print(f"{i + 1:,}건 생성 완료...")

    print(f"부하 테스트 전용 데이터 생성 완료, 파일명: {filename}")

if __name__ == "__main__":
    generate_candles()
