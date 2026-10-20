/**
 * 주가 데이터 정렬 처리를 위한 Web Worker
 */
self.onmessage = (e: MessageEvent) => {
	const { updates, stockMapEntries, type, limit } = e.data;

	console.log('[Worker] received message, updates:', updates?.length, 'type:', type);

	// 배열로 받은 entries를 Map으로 복원
	const newMap = new Map(stockMapEntries);
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

	console.log('[Worker] posting result, sortedCodes:', sortedCodes.length);

	// Map을 배열로 직렬화해서 반환
	self.postMessage({
		newMapEntries: Array.from(newMap.entries()),
		sortedCodes,
	});
};