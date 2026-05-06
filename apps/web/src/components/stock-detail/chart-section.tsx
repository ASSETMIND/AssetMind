import { useParams } from 'react-router-dom';
import { useCandlestickChart, PERIOD_TABS } from '../../hooks/stock-detail/use-candlestick-chart';

export default function ChartSection() {
	const { id: stockCode = '' } = useParams<{ id: string }>();
	const { chartContainerRef, period, setPeriod, isLoading, isError } = useCandlestickChart(stockCode);

	return (
		<div
			style={{
				backgroundColor: '#1C1D21',
				borderRadius: '12px',
				padding: '16px',
				display: 'flex',
				flexDirection: 'column',
				gap: '12px',
				height: '500px',
			}}
		>
			{/* 기간 탭 */}
			<div style={{ display: 'flex', gap: '4px', position: 'relative', zIndex: 10 }}>
				{PERIOD_TABS.map((tab) => (
					<button
						key={tab}
						onClick={() => setPeriod(tab)}
						style={{
							padding: '4px 12px',
							borderRadius: '6px',
							border: 'none',
							cursor: 'pointer',
							fontSize: '13px',
							fontWeight: period === tab ? 700 : 400,
							backgroundColor: period === tab ? '#2C2C30' : 'transparent',
							color: period === tab ? '#FFFFFF' : '#9194A1',
							transition: 'background-color 0.15s, color 0.15s',
							position: 'relative',
							zIndex: 10,
						}}
					>
						{tab}
					</button>
				))}
			</div>

			{/* 차트 영역 */}
			<div style={{ flex: 1, position: 'relative' }}>
				{isLoading && (
					<div style={{
						position: 'absolute', inset: 0,
						display: 'flex', alignItems: 'center', justifyContent: 'center',
						backgroundColor: '#1C1D21',
					}}>
						<div
							style={{
								width: '32px', height: '32px',
								border: '3px solid #2F3037',
								borderTopColor: '#EA580C',
								borderRadius: '50%',
								animation: 'spin 0.8s linear infinite',
							}}
						/>
						<style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
					</div>
				)}
				{isError && (
					<div style={{
						position: 'absolute', inset: 0,
						display: 'flex', alignItems: 'center', justifyContent: 'center',
						color: '#9194A1', fontSize: '14px',
					}}>
						차트 데이터를 불러오지 못했습니다.
					</div>
				)}
				<div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
			</div>
		</div>
	);
}