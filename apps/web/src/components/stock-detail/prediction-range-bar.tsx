const RISE_COLOR = '#EA580C';
const FALL_COLOR = '#256AF4';
const BAR_BG = '#2A2A2E';
const MIN_BAR_PCT = 4;

function formatPrice(value: number): string {
	return Math.abs(value).toLocaleString('ko-KR');
}

function clampBar(pct: number): number {
	if (pct <= 0) return 0;
	return Math.max(pct, MIN_BAR_PCT);
}

export interface PredictionRangeBarProps {
	predictedPrice: number;
	priceDiff: number;
	changeRate: number;
	baseDate: string;
	upProbability: number;
	downProbability: number;
}

interface DirectionBarProps {
	label: string;
	probability: number;
	barPct: number;
	color: string;
}

const DirectionBar = ({ label, probability, barPct, color }: DirectionBarProps) => (
	<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
		<span style={{ width: '25px', height: '18px', fontSize: '12px', fontWeight: 700, color, display: 'flex', alignItems: 'center', flexShrink: 0 }}>{label}</span>
		<div style={{ flex: 1, height: '10px', backgroundColor: BAR_BG, borderRadius: '9999px', overflow: 'hidden', position: 'relative' }}>
			<div style={{ width: `${barPct}%`, height: '100%', backgroundColor: color, borderRadius: '9999px', transition: 'width 0.4s ease' }} />
		</div>
		<span style={{ width: '25px', height: '18px', fontSize: '12px', fontWeight: 700, color, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{probability}%</span>
	</div>
);

export const PredictionRangeBar = ({ predictedPrice, priceDiff, changeRate, baseDate, upProbability, downProbability }: PredictionRangeBarProps) => {
	const isRise = priceDiff >= 0;
	const diffColor = isRise ? RISE_COLOR : FALL_COLOR;
	const diffSign = isRise ? '+' : '-';
	const upBarPct = clampBar(upProbability);
	const downBarPct = clampBar(downProbability);

	return (
		<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
			<div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
				<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>AI 예측가</span>
					<span style={{ fontSize: '10px', fontWeight: 400, color: '#9F9F9F' }}>{baseDate} 기준</span>
				</div>
				<div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
					<span style={{ fontSize: '24px', fontWeight: 700, color: '#FFFFFF', fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.5px' }}>
						{formatPrice(predictedPrice)}원
					</span>
					<span style={{ fontSize: '14px', fontWeight: 500, color: diffColor, fontVariantNumeric: 'tabular-nums' }}>
						{diffSign}{formatPrice(priceDiff)}원 ({isRise ? '+' : '-'}{Math.abs(changeRate).toFixed(2)}%)
					</span>
				</div>
			</div>
			<div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
				<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>방향성 확률</span>
				<DirectionBar label="상승" probability={upProbability} barPct={upBarPct} color={RISE_COLOR} />
				<DirectionBar label="하락" probability={downProbability} barPct={downBarPct} color={FALL_COLOR} />
			</div>
		</div>
	);
};

export default PredictionRangeBar;
