import { render, screen } from '@testing-library/react';
import StockItem, {
	type StockItemData,
} from '../../components/stock/stock-item';
import { useStockItemLogic } from '../../hooks/stock/use-stock-item-logic';

/**
 * [Mocking 설정]
 * - 비즈니스 로직(useStockItemLogic)을 모킹하여 계산 로직과 UI 렌더링을 분리합니다.
 * - 하위 컴포넌트(RatioBar)를 모킹하여 StockItem 자체의 렌더링에만 집중합니다.
 */
jest.mock('../../hooks/stock/use-stock-item-logic');

jest.mock('../../components/stock/ratio-bar', () => () => (
	<div data-testid='ratio-bar' />
));

describe('StockItem Component', () => {
	// 테스트용 모의 데이터
	const mockData: StockItemData = {
		id: '005930',
		rank: 1,
		name: '삼성전자',
		price: '70,000',
		changeRate: 1.5,
		tradeVolume: '5,000억원',
		buyRatio: 60,
		sellRatio: 40,
	};

	beforeEach(() => {
		// 훅이 반환할 가공된 데이터를 미리 설정 (양수 변동률 및 빨간색 스타일)
		(useStockItemLogic as jest.Mock).mockReturnValue({
			formattedChangeRate: '+1.50%',
			badgeClass: 'text-red-500 bg-red-500/20',
		});
	});

	it('전달받은 주식 정보를 화면에 올바르게 렌더링해야 한다', () => {
		/**
		 * @Given
		 * - 삼성전자 주식 데이터(mockData) 준비
		 */

		/**
		 * @When
		 * - StockItem 컴포넌트를 렌더링
		 */
		render(<StockItem data={mockData} />);

		/**
		 * @Then
		 * - 순위, 이름, 가격(원 접미사 포함), 거래대금이 화면에 표시되는지 확인
		 * - 모킹된 RatioBar가 포함되어 있는지 확인
		 */
		expect(screen.getByText('1')).toBeInTheDocument();
		expect(screen.getByText('삼성전자')).toBeInTheDocument();
		expect(screen.getByText('70,000원')).toBeInTheDocument();
		expect(screen.getByText('5,000억원')).toBeInTheDocument();
		expect(screen.getByTestId('ratio-bar')).toBeInTheDocument();
	});

	it('useStockItemLogic에서 반환된 스타일과 텍스트를 적용해야 한다', () => {
		/**
		 * @Given
		 * - 훅이 '+1.50%'와 특정 클래스명을 반환하도록 설정됨 (beforeEach)
		 */

		/**
		 * @When
		 * - StockItem 컴포넌트를 렌더링
		 */
		render(<StockItem data={mockData} />);

		/**
		 * @Then
		 * - 훅에서 전달한 포맷팅된 텍스트('+1.50%')가 렌더링되었는지 확인
		 * - 해당 요소가 올바른 스타일 클래스(text-red-500 등)를 가지고 있는지 확인
		 */
		const badge = screen.getByText('+1.50%');
		expect(badge).toBeInTheDocument();
		expect(badge).toHaveClass('text-red-500 bg-red-500/20');
	});

	it('하트 아이콘과 로고 영역이 존재해야 한다', () => {
		/**
		 * @Given
		 * - 컴포넌트 렌더링 준비
		 */

		/**
		 * @When
		 * - StockItem 컴포넌트 렌더링
		 */
		render(<StockItem data={mockData} />);

		/**
		 * @Then
		 * - 즐겨찾기(하트) 및 로고 표시 영역이 정적으로 존재하는지 확인
		 */
		expect(screen.getByText('♥')).toBeInTheDocument();
		expect(screen.getByText('로고')).toBeInTheDocument();
	});
});
