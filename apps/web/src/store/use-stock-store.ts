import { create } from 'zustand';
import type { StockRankingDto } from '../types/stock';

interface StockState {
	stockMap: Map<string, StockRankingDto>;
	stockCodes: string[];
	mapVersion: number;
	setInitialStocks: (stocks: StockRankingDto[]) => void;
	updateStocks: (updates: StockRankingDto[], type: 'VALUE' | 'VOLUME', limit: number) => void;
}

export const useStockStore = create<StockState>((set, get) => ({
	stockMap: new Map(),
	stockCodes: [],
	mapVersion: 0,

	setInitialStocks: (stocks) => set({
		stockMap: new Map(stocks.map((s) => [s.stockCode, s])),
		stockCodes: stocks.map((s) => s.stockCode),
	}),

	updateStocks: (updates, type, limit) => {
		const { stockMap } = get();

		// Worker 없이 메인 스레드에서 직접 처리
		const newMap = new Map(stockMap);
		updates.forEach((s) => newMap.set(s.stockCode, s));

		const sortedList = Array.from(newMap.values())
			.sort((a, b) =>
				type === 'VALUE'
					? b.cumulativeAmount - a.cumulativeAmount
					: b.cumulativeVolume - a.cumulativeVolume,
			)
			.slice(0, limit);

		const sortedCodes = sortedList.map((s) => s.stockCode);

		set((state) => ({
			stockMap: newMap,
			stockCodes: sortedCodes,
			mapVersion: state.mapVersion + 1,
		}));
	},
}));