import { useParams } from 'react-router-dom';
import { useStockDetail } from '../../hooks/stock-detail/use-stock-detail';

export default function StockHeaderCard() {
	const { id: stockCode = '' } = useParams<{ id: string }>();
	const { data, isConnected } = useStockDetail(stockCode);

	const isRise = (data?.changeRate ?? 0) > 0;
	const isFall = (data?.changeRate ?? 0) < 0;
	const changeColor = isRise ? '#EA580C' : isFall ? '#256AF4' : '#9194A1';

	const formattedPrice = data
		? data.currentPrice.toLocaleString('ko-KR') + '원'
		: '--';

	const formattedChange = data
		? `${data.priceChange >= 0 ? '+' : ''}${data.priceChange.toLocaleString('ko-KR')}원 (${data.changeRate >= 0 ? '+' : ''}${data.changeRate.toFixed(2)}%)`
		: '--';

	return (
		<div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
			{/* 로고 */}
			<div style={{
				width: '48px', height: '48px',
				backgroundColor: '#21242C',
				borderRadius: '8px',
				flexShrink: 0,
			}} />

			{/* 종목 정보 */}
			<div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
				{/* 종목명 + 코드 */}
				<div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
					<h1 style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF', margin: 0 }}>
						종목명
					</h1>
					<span style={{ fontSize: '13px', fontWeight: 400, color: '#9194A1' }}>
						{stockCode}
					</span>
				</div>

				{/* 현재가 + 등락 */}
				<div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
					<span style={{
						fontSize: '22px', fontWeight: 700, color: '#FFFFFF',
						fontVariantNumeric: 'tabular-nums',
					}}>
						{formattedPrice}
					</span>
					<span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1' }}>
						어제보다
					</span>
					<span style={{
						fontSize: '13px', fontWeight: 500,
						color: changeColor,
						fontVariantNumeric: 'tabular-nums',
					}}>
						{formattedChange}
					</span>
				</div>

				{/* 연결 상태 표시 */}
				{!isConnected && (
					<span style={{ fontSize: '11px', color: '#9194A1' }}>
						실시간 연결 중...
					</span>
				)}
			</div>
		</div>
	);
}