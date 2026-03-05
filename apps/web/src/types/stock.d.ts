export interface StockRankingDto {
	stockCode: string; // 종목 코드
	stockName: string; // 종목 이름
	currentPrice: number; // 현재가
	changeRate: number; // 등락률
	cumulativeAmount: number; // 누적 거래 대금
	cumulativeVolume: number; // 누적 거래량
}
