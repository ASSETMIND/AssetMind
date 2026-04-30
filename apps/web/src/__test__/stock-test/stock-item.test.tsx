import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import StockItem, {
	type StockItemData,
} from '../../components/stock-main/stock-item';
import { useStockItemLogic } from '../../hooks/stock/use-stock-item-logic';

// react-router-dom의 useNavigate 모킹
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
	...jest.requireActual('react-router-dom'),
	useNavigate: () => mockNavigate,
}));

// 비즈니스 로직(useStockItemLogic) 모킹
jest.mock('../../hooks/stock/use-stock-item-logic');

// 하위 컴포넌트(RatioBar) 모킹
jest.mock('../../components/stock-main/ratio-bar', () => () => (
	<div data-testid='ratio-bar' />
));

describe('StockItem Component', () => {
	// 테스트용 모의 데이터
	const mockData: StockItemData = {
		stockCode: '005930',
		rank: 1,
		stockName: '삼성전자',
		price: '70,000',
		changeRate: 1.5,
		tradeVolume: '5,000억원',
		buyRatio: 60,
		sellRatio: 40,
	};

	beforeEach(() => {
		jest.clearAllMocks();

		// 훅이 반환할 가공된 데이터를 미리 설정
		(useStockItemLogic as jest.Mock).mockReturnValue({
			name: '삼성전자',
			formattedChangeRate: '+1.50%',
			textColorClass: 'text-red-500',
			flashBgClass: 'bg-red-500/20',
			isPositive: true,
			isNegative: false,
		});
	});

	const renderWithRouter = (ui: React.ReactElement) => {
		return render(<BrowserRouter>{ui}</BrowserRouter>);
	};

	it('전달받은 주식 정보를 화면에 올바르게 렌더링해야 한다', () => {
		renderWithRouter(<StockItem data={mockData} />);

		// 순위, 이름, 가격, 거래대금 확인
		expect(screen.getByText('1')).toBeInTheDocument();
		expect(screen.getByText('삼성전자')).toBeInTheDocument();
		expect(screen.getByText('70,000원')).toBeInTheDocument();
		expect(screen.getByText('5,000억원')).toBeInTheDocument();

		// 모킹된 RatioBar 확인
		expect(screen.getByTestId('ratio-bar')).toBeInTheDocument();
	});

	it('useStockItemLogic에서 반환된 스타일과 텍스트를 적용해야 한다', () => {
		renderWithRouter(<StockItem data={mockData} />);

		const badge = screen.getByText('+1.50%');
		expect(badge).toBeInTheDocument();
		// 최신 textColorClass 적용 확인
		expect(badge).toHaveClass('text-red-500');
	});

	it('아이템 클릭 시 해당 주식 상세 페이지로 이동해야 한다', () => {
		renderWithRouter(<StockItem data={mockData} />);

		// 전체 컨테이너 클릭 (grid 레이아웃을 가진 div 찾기)
		const container = screen.getByText('삼성전자').closest('div.grid');
		if (container) {
			fireEvent.click(container);
		}

		expect(mockNavigate).toHaveBeenCalledWith('/stock/005930');
	});

	it('하트 버튼 클릭 시 이벤트 전파(Propagation)가 중단되어야 한다', () => {
		renderWithRouter(<StockItem data={mockData} />);

		const favoriteButton = screen.getByLabelText('삼성전자 관심종목 추가');

		// 클릭 이벤트 발생
		fireEvent.click(favoriteButton);

		// 네비게이션이 호출되지 않아야 함 (전파 중단 확인)
		expect(mockNavigate).not.toHaveBeenCalled();
	});

	it('하트 아이콘과 로고 영역이 존재해야 한다', () => {
		renderWithRouter(<StockItem data={mockData} />);

		expect(screen.getByText('♥')).toBeInTheDocument();
		expect(screen.getByText('로고')).toBeInTheDocument();
	});
});
