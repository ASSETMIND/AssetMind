import type { RankingType } from '../../types/stock';

interface Props {
	activeType: RankingType;
	onTypeChange: (type: RankingType) => void;
}

export default function StockFilterGroup({ activeType, onTypeChange }: Props) {
	const wrapperStyle: React.CSSProperties = {
		display: 'flex',
		alignItems: 'center',
		borderRadius: '12px',
		backgroundColor: '#1C1D21',
		padding: '4px',
		gap: '2px',
	};

	const activeBtn: React.CSSProperties = {
		borderRadius: '8px',
		backgroundColor: '#2C2C30',
		padding: '6px 12px',
		fontSize: '13px',
		fontWeight: 600,
		color: '#FFFFFF',
		border: 'none',
		cursor: 'pointer',
		whiteSpace: 'nowrap',
		transition: 'background-color 0.15s',
	};

	const inactiveBtn: React.CSSProperties = {
		borderRadius: '8px',
		backgroundColor: 'transparent',
		padding: '6px 12px',
		fontSize: '13px',
		fontWeight: 400,
		color: '#9194A1',
		border: 'none',
		cursor: 'pointer',
		whiteSpace: 'nowrap',
		transition: 'background-color 0.15s',
	};

	return (
		<div
			style={{
				display: 'flex',
				gap: '12px',
				padding: '16px 0',
				overflowX: 'auto',
				width: '100%',
			}}
		>
			{/* 지역 필터 */}
			<div style={wrapperStyle}>
				<button style={activeBtn}>전체</button>
				<button style={inactiveBtn}>국내</button>
				<button style={inactiveBtn}>해외</button>
			</div>

			{/* 정렬 기준 필터 */}
			<div style={wrapperStyle}>
				<button
					style={activeType === 'VALUE' ? activeBtn : inactiveBtn}
					onClick={() => onTypeChange('VALUE')}
				>
					거래대금순
				</button>
				<button
					style={activeType === 'VOLUME' ? activeBtn : inactiveBtn}
					onClick={() => onTypeChange('VOLUME')}
				>
					거래량순
				</button>
			</div>

			{/* 시간 필터 */}
			<div style={wrapperStyle}>
				<button style={activeBtn}>실시간</button>
				<button style={inactiveBtn}>1일</button>
				<button style={inactiveBtn}>1주일</button>
				<button style={inactiveBtn}>1개월</button>
				<button style={inactiveBtn}>3개월</button>
				<button style={inactiveBtn}>6개월</button>
				<button style={inactiveBtn}>1년</button>
			</div>
		</div>
	);
}