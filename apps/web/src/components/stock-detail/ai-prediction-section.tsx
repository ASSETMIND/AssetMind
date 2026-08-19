import { useState } from 'react';
import { useViewport } from '../../hooks/common/use-viewport';
import { BuyIcon } from '../icon/buy-icon';
import { MoonIcon } from '../icon/moon-icon';
import { SparklineChart } from './sparkline-chart';
import type { SparklineDataPoint } from './sparkline-chart';
import { PredictionRangeBar } from './prediction-range-bar';
import { PredictionAnalysisWidget } from './prediction-analysis-widget';
import type { AnalysisData } from './prediction-analysis-widget';

// ─── Types ────────────────────────────────────────────────────

type PeriodTab = '1주' | '1개월' | '3개월';
type PanelStatus = 'default' | 'skeleton' | 'error' | 'empty';

const PERIODS: PeriodTab[] = ['1주', '1개월', '3개월'];

// ─── Mock 데이터 (API 연동 전 임시) ──────────────────────────

const MOCK_HISTORICAL: SparklineDataPoint[] = Array.from({ length: 14 }, (_, i) => ({
	time: `2026-05-${String(i + 1).padStart(2, '0')}`,
	value: 75000 + Math.sin(i * 0.5) * 3000 + i * 200,
}));

const MOCK_FORECAST: SparklineDataPoint[] = Array.from({ length: 7 }, (_, i) => ({
	time: `2026-05-${String(i + 15).padStart(2, '0')}`,
	value: 78000 + Math.cos(i * 0.4) * 2000 + i * 300,
}));

const MOCK_ANALYSIS: AnalysisData = {
	'기술적 지표': [
		{ type: 'positive', text: 'MACD 골든크로스 신호 감지' },
		{ type: 'warning',  text: 'RSI 과매수 구간 진입 주의' },
		{ type: 'neutral',  text: '볼린저 밴드 중단 횡보 중' },
	],
	'시장 심리': [
		{ type: 'positive', text: '외국인 순매수 3일 연속 지속' },
		{ type: 'neutral',  text: '기관 매도세 소폭 완화' },
		{ type: 'warning',  text: '공매도 비중 증가 추세' },
	],
	'수급 동향': [
		{ type: 'positive', text: '프로그램 매수 우위' },
		{ type: 'neutral',  text: '거래량 20일 평균 수준 유지' },
		{ type: 'warning',  text: '대차잔고 증가 모니터링 필요' },
	],
};

// ─── Skeleton ─────────────────────────────────────────────────

const SkeletonBox = ({ width = '100%', height = 16, borderRadius = 6 }: { width?: string | number; height?: number; borderRadius?: number }) => (
	<div style={{ width, height: `${height}px`, borderRadius: `${borderRadius}px`, backgroundColor: '#21242C', flexShrink: 0 }} />
);

const PanelSkeleton = () => (
	<>
		<SkeletonBox height={140} borderRadius={8} />
		<div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
			<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>AI 예측가</span>
			<div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
				<SkeletonBox width={140} height={32} borderRadius={6} />
				<SkeletonBox width={100} height={20} borderRadius={6} />
			</div>
		</div>
		<div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
			<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>방향성 확률</span>
			{(['상승', '하락'] as const).map((label, i) => (
				<div key={label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
					<span style={{ fontSize: '12px', fontWeight: 700, color: i === 0 ? '#EA580C' : '#256AF4', width: '25px', flexShrink: 0 }}>{label}</span>
					<SkeletonBox height={8} borderRadius={9999} />
					<span style={{ fontSize: '12px', fontWeight: 700, color: i === 0 ? '#EA580C' : '#256AF4', width: '25px', textAlign: 'right', flexShrink: 0 }}>-</span>
				</div>
			))}
		</div>
		<div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
			<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>분석 근거</span>
			<div style={{ display: 'flex', gap: '10px' }}>
				{[90, 80, 80].map((w, i) => <SkeletonBox key={i} width={w} height={34} borderRadius={30} />)}
			</div>
			<div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '10px', backgroundColor: '#131316', borderRadius: '8px' }}>
				{[1, 2, 3, 4, 5].map((i) => <SkeletonBox key={i} height={28} borderRadius={8} />)}
			</div>
		</div>
	</>
);

// ─── Period Tabs ──────────────────────────────────────────────

const PeriodTabs = ({ active, onSelect }: { active: PeriodTab; onSelect: (p: PeriodTab) => void }) => (
	<div style={{ display: 'flex', gap: '4px', height: '48px', alignItems: 'center' }}>
		{PERIODS.map((p) => {
			const isActive = active === p;
			return (
				<button key={p} onClick={() => onSelect(p)} style={{ flex: 1, height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: isActive ? '#2C2C30' : 'transparent', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '16px', fontWeight: isActive ? 700 : 400, color: isActive ? '#FFFFFF' : '#9F9F9F', transition: 'background-color 0.15s ease, color 0.15s ease' }}>
					{p}
				</button>
			);
		})}
	</div>
);

// ─── AIPredictionSection ──────────────────────────────────────

export default function AIPredictionSection() {
	const viewport = useViewport();
	const [activePeriod, setActivePeriod] = useState<PeriodTab>('1주');
	const status: PanelStatus = 'default';

	const isMobile = viewport === 'mobile';
	const isTablet = viewport === 'tablet';
	const panelWidth = '100%';
	const panelHeight = isMobile ? 'auto' : '820px';

	return (
		<div style={{ width: panelWidth, height: panelHeight, maxHeight: isMobile ? 'none' : '100vh', overflowY: isMobile ? 'visible' : 'auto', backgroundColor: '#1C1D21', borderRadius: '12px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '10px', boxSizing: 'border-box' }}>
			{/* 헤더 */}
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
				<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>AI 가격 예측 패널</span>
				{status === 'empty' ? (
					<div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '5px', backgroundColor: '#2C2C30', borderRadius: '4px', width: '64px', height: '25px', boxSizing: 'border-box' }}>
						<MoonIcon color="#FFFFFF" width={12} height={14} />
						<span style={{ fontSize: '10px', fontWeight: 500, color: '#FFFFFF', whiteSpace: 'nowrap' }}>휴장 시간</span>
					</div>
				) : (
					<button style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'none', border: '1px solid #2F3037', cursor: 'pointer', padding: '4px 8px', borderRadius: '4px' }}>
						<BuyIcon color="#9F9F9F" />
						<span style={{ fontSize: '14px', fontWeight: 400, color: '#9F9F9F' }}>매수하기</span>
					</button>
				)}
			</div>

			{/* 본문 */}
			<div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flexShrink: 0 }}>
				{status === 'error' ? (
					<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '600px', gap: '16px' }}>
						<p style={{ fontSize: '14px', color: '#9F9F9F', textAlign: 'center', lineHeight: '1.6', margin: 0 }}>
							예측 데이터를 불러오지 못했습니다.<br />잠시 후 다시 시도해 주세요.
						</p>
						<button onClick={() => window.location.reload()} style={{ width: '100px', height: '38px', backgroundColor: '#6D4AE6', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#FFFFFF' }}>
							다시 시도
						</button>
					</div>
				) : (
					<>
						<PeriodTabs active={activePeriod} onSelect={setActivePeriod} />
						{status === 'skeleton' ? (
							<PanelSkeleton />
						) : (
							<>
								<SparklineChart historicalData={MOCK_HISTORICAL} forecastData={MOCK_FORECAST} width="100%" />
								<PredictionRangeBar
									predictedPrice={82000}
									priceDiff={7000}
									changeRate={9.33}
									baseDate="2026년 05월 18일"
									upProbability={68}
									downProbability={32}
								/>
								<PredictionAnalysisWidget data={MOCK_ANALYSIS} />
								<span style={{ fontSize: '11px', fontWeight: 400, color: '#9F9F9F', lineHeight: '1.6', paddingTop: '4px' }}>
									※ AI 예측은 참고로만 이용하며 투자 판단의 방적 근거가 될 수 없습니다. 투자 손실의 책임은 투자자 본인에게 있습니다.
								</span>
							</>
						)}
					</>
				)}
			</div>
		</div>
	);
}