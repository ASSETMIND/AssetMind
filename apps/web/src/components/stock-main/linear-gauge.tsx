interface LinearGaugeProps {
	buyRatio: number; // 0~100 매수 비율
	className?: string;
}

export const LinearGauge = ({ buyRatio, className }: LinearGaugeProps) => {
	const sellRatio = 100 - buyRatio;
	const BAR_WIDTH = 120;
	const MIN_PX = 4;

	let buyPx = Math.round((buyRatio / 100) * BAR_WIDTH);
	let sellPx = BAR_WIDTH - buyPx;

	if (buyRatio > 0 && buyPx < MIN_PX) { buyPx = MIN_PX; sellPx = BAR_WIDTH - MIN_PX; }
	if (sellRatio > 0 && sellPx < MIN_PX) { sellPx = MIN_PX; buyPx = BAR_WIDTH - MIN_PX; }
	if (buyRatio === 0) { buyPx = 0; sellPx = BAR_WIDTH; }
	if (sellRatio === 0) { sellPx = 0; buyPx = BAR_WIDTH; }

	return (
		<div
			className={className}
			style={{
				display: 'flex',
				flexDirection: 'column',
				alignItems: 'center',
				gap: '2px',
			}}
		>
			{/* 바 — 120x4 */}
			<div
				style={{
					width: '120px',
					height: '4px',
					display: 'flex',
					borderRadius: '9999px',
					overflow: 'hidden',
				}}
			>
				<div style={{ width: `${buyPx}px`, height: '100%', backgroundColor: '#256AF4', flexShrink: 0 }} />
				<div style={{ width: `${sellPx}px`, height: '100%', backgroundColor: '#EA580C', flexShrink: 0 }} />
			</div>

			{/* 라벨 */}
			<div style={{ width: '120px', display: 'flex', justifyContent: 'space-between' }}>
				<span style={{ fontSize: '10px', fontWeight: 500, color: '#256AF4', fontVariantNumeric: 'tabular-nums' }}>
					{buyRatio}
				</span>
				<span style={{ fontSize: '10px', fontWeight: 500, color: '#EA580C', fontVariantNumeric: 'tabular-nums' }}>
					{sellRatio}
				</span>
			</div>
		</div>
	);
};

export default LinearGauge;