import { create } from 'zustand';
import type { StockRankingDto } from '../types/stock';

interface StockState {
	stockMap: Map<string, StockRankingDto>;
	stockCodes: string[];
	
	setInitialStocks: (stocks: StockRankingDto[]) => void;
	updateStocks: (updates: StockRankingDto[], type: 'VALUE' | 'VOLUME', limit: number) => void;
}

// Web Worker 인스턴스 생성 (Vite 전용 URL 문법)
const stockWorker = new Worker(new URL('../workers/stock-worker.ts', import.meta.url), {
	type: 'module'
});

export const useStockStore = create<StockState>((set, get) => {
	// Worker 결과 수신 리스너 등록
	stockWorker.onmessage = (e) => {
		const { newMap, sortedCodes } = e.data;
		set({ stockMap: newMap, stockCodes: sortedCodes });
	};

	return {
		stockMap: new Map(),
		stockCodes: [],

		setInitialStocks: (stocks) => set({
			stockMap: new Map(stocks.map(s => [s.stockCode, s])),
			stockCodes: stocks.map(s => s.stockCode)
		}),

		updateStocks: (updates, type, limit) => {
			const { stockMap } = get();
			
			// 무거운 연산(정렬)을 Worker로 위임
			stockWorker.postMessage({
				updates,
				stockMap,
				type,
				limit
			});
		}
	};
});
