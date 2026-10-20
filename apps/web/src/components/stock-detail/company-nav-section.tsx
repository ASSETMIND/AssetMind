const LEFT_TABS = [
	{ id: 'main',     label: '주요 정보' },
	{ id: 'finance',  label: '재무' },
	{ id: 'result',   label: '실적' },
	{ id: 'dividend', label: '배당' },
	{ id: 'peer',     label: '동종 업계 비교' },
	{ id: 'analyst',  label: '애널리스트 분석' },
];

interface CompanyNavSectionProps {
	activeTab: string;
	onTabClick: (id: string) => void;
}

export default function CompanyNavSection({ activeTab, onTabClick }: CompanyNavSectionProps) {
	return (
		<div style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '8px 0' }}>
			{LEFT_TABS.map((tab) => (
				<button
					key={tab.id}
					onClick={() => onTabClick(tab.id)}
					style={{
						width: '100%',
						padding: '10px 16px',
						backgroundColor: activeTab === tab.id ? '#21242C' : 'transparent',
						border: 'none',
						borderRadius: activeTab === tab.id ? '8px' : 0,
						cursor: 'pointer',
						textAlign: 'left',
						fontSize: '16px',
						fontWeight: activeTab === tab.id ? 700 : 400,
						color: activeTab === tab.id ? '#FFFFFF' : '#9194A1',
						transition: 'background-color 0.15s ease',
					}}
				>
					{tab.label}
				</button>
			))}
		</div>
	);
}
