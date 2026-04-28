import { z } from 'zod';

// 개별 주식 랭킹 아이템 스키마
export const StockRankingItemSchema = z.object({
	stockCode: z.string(),
	stockName: z.string(),
	currentPrice: z.coerce.number(), // 문자열로 올 경우 숫자로 변환
	changeRate: z.coerce.number(),
	cumulativeAmount: z.coerce.number(),
	cumulativeVolume: z.coerce.number(),
});

// 웹소켓 응답 메시지 전체 스키마
export const StockRankingResponseSchema = z.object({
	type: z.string(),
	data: z.array(StockRankingItemSchema),
});
