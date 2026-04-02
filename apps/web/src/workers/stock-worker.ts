/**
 * 주식 데이터 연산 처리를 위한 Web Worker
 * - 메인 스레드 부하를 줄이기 위해 정렬 및 필터링 연산을 수행합니다.
 */

self.onmessage = (e: MessageEvent) => {
	const { updates, stockMap, type, limit } = e.data;

	// 새로운 업데이트를 맵에 반영 (복사본 생성)
	const newMap = new Map(stockMap);
	updates.forEach((s: any) => newMap.set(s.stockCode, s));

	// 정렬 수행
	const sortedList = Array.from(newMap.values())
		.sort((a: any, b: any) => {
			if (type === 'VALUE') {
				return b.cumulativeAmount - a.cumulativeAmount;
			} else {
				return b.cumulativeVolume - a.cumulativeVolume;
			}
		})
		.slice(0, limit);

	const sortedCodes = sortedList.map((s: any) => s.stockCode);

	// 결과 반환
	self.postMessage({
		newMap,
		sortedCodes,
	});
};
