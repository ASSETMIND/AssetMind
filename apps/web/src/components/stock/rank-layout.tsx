import StockFilterGroup from './stock-filter-group';
import StockItem, { type StockItemData } from './stock-item';
import TableHeader from './table-header';

// 확인을 위한 임시 데이터
const MOCK_DATA: StockItemData[] = [
	{
		id: 1,
		rank: 1,
		name: '현대차',
		price: '517,000',
		changeRate: 3.6,
		tradeVolume: '379억원',
		buyRatio: 75,
		sellRatio: 25,
	},
	{
		id: 2,
		rank: 2,
		name: '삼성전자',
		price: '188,700',
		changeRate: 4.13,
		tradeVolume: '91억원',
		buyRatio: 38,
		sellRatio: 62,
	},
	{
		id: 3,
		rank: 3,
		name: '한온시스템',
		price: '5,670',
		changeRate: 27.13,
		tradeVolume: '82억원',
		buyRatio: 43,
		sellRatio: 57,
	},
	{
		id: 4,
		rank: 4,
		name: 'SK하이닉스',
		price: '890,000',
		changeRate: 1.13,
		tradeVolume: '75억원',
		buyRatio: 21,
		sellRatio: 79,
	},
	{
		id: 5,
		rank: 5,
		name: 'KODEX 코스닥150레버리지',
		price: '18,900',
		changeRate: 13.44,
		tradeVolume: '68억원',
		buyRatio: 71,
		sellRatio: 29,
	},
	{
		id: 6,
		rank: 6,
		name: '에코프로',
		price: '170,300',
		changeRate: 13.23,
		tradeVolume: '45억원',
		buyRatio: 60,
		sellRatio: 40,
	},
	{
		id: 7,
		rank: 7,
		name: 'KODEX 레버리지',
		price: '89,355',
		changeRate: 5.6,
		tradeVolume: '39억원',
		buyRatio: 55,
		sellRatio: 45,
	},
	{
		id: 8,
		rank: 8,
		name: '한화솔루션',
		price: '55,800',
		changeRate: 21.56,
		tradeVolume: '35억원',
		buyRatio: 53,
		sellRatio: 47,
	},
	{
		id: 9,
		rank: 9,
		name: '현대ADM',
		price: '9,370',
		changeRate: 26.96,
		tradeVolume: '32억원',
		buyRatio: 51,
		sellRatio: 49,
	},
	{
		id: 10,
		rank: 10,
		name: '미래에셋증권',
		price: '70,800',
		changeRate: 14.93,
		tradeVolume: '28억원',
		buyRatio: 47,
		sellRatio: 53,
	},
	{
		id: 11,
		rank: 11,
		name: 'KODEX 코스닥150',
		price: '20,230',
		changeRate: 6.72,
		tradeVolume: '27억원',
		buyRatio: 69,
		sellRatio: 31,
	},
	{
		id: 12,
		rank: 12,
		name: '삼성전기',
		price: '359,000',
		changeRate: 15.99,
		tradeVolume: '21억원',
		buyRatio: 49,
		sellRatio: 51,
	},
	{
		id: 13,
		rank: 13,
		name: '대동기어',
		price: '26,200',
		changeRate: 3.96,
		tradeVolume: '21억원',
		buyRatio: 49,
		sellRatio: 51,
	},
	{
		id: 14,
		rank: 14,
		name: '두산에너빌리티',
		price: '98,800',
		changeRate: 2.17,
		tradeVolume: '20억원',
		buyRatio: 32,
		sellRatio: 68,
	},
	{
		id: 15,
		rank: 15,
		name: '기아',
		price: '170,200',
		changeRate: 3.71,
		tradeVolume: '18억원',
		buyRatio: 75,
		sellRatio: 25,
	},
	{
		id: 16,
		rank: 16,
		name: '우리기술',
		price: '12,870',
		changeRate: 4.29,
		tradeVolume: '16억원',
		buyRatio: 49,
		sellRatio: 51,
	},
	{
		id: 17,
		rank: 17,
		name: 'KODEX 200',
		price: '84,200',
		changeRate: 2.85,
		tradeVolume: '16억원',
		buyRatio: 51,
		sellRatio: 49,
	},
	{
		id: 18,
		rank: 18,
		name: '한화오션',
		price: '140,700',
		changeRate: 8.39,
		tradeVolume: '15억원',
		buyRatio: 59,
		sellRatio: 41,
	},
	{
		id: 19,
		rank: 19,
		name: 'LG전자',
		price: '122,200',
		changeRate: 4.26,
		tradeVolume: '14억원',
		buyRatio: 67,
		sellRatio: 33,
	},
	{
		id: 20,
		rank: 20,
		name: '한미반도체',
		price: '201,000',
		changeRate: -0.74,
		tradeVolume: '12억원',
		buyRatio: 24,
		sellRatio: 76,
	},
];

// 랭킹 페이지의 전체 레이아웃 담당
export default function RankLayout() {
	return (
		<div className='w-full max-w-6xl mx-auto px-4'>
			{/* 필터 영역 */}
			<StockFilterGroup />

			{/* 랭킹 리스트 영역 */}
			<div className='rounded-lg'>
				<TableHeader />
				<div className='flex flex-col'>
					{MOCK_DATA.map((item) => (
						<StockItem key={item.id} data={item} />
					))}
				</div>
			</div>
		</div>
	);
}
