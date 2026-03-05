import { render, screen, fireEvent } from '@testing-library/react';
import RankLayout from '../../components/stock/rank-layout';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';

/**
 * [Mocking 설정]
 * 외부 의존성(WebSocket URL, 데이터 로직 훅, 하위 UI 컴포넌트)을 가짜(Mock)로 대체하여
 * RankLayout의 "연결 로직"에만 집중할 수 있는 환경을 만듭니다.
 */
jest.mock('../../api/stock', () => ({
	STOCK_WS_URL: 'ws://localhost:8080/stocks',
}));

jest.mock('../../hooks/stock/use-stock-rank-logic');

jest.mock(
	'../../components/stock/stock-filter-group',
	() =>
		({ activeType, onTypeChange }: any) => (
			<div data-testid='filter-group'>
				<button onClick={() => onTypeChange('VALUE')}>VALUE</button>
				<button onClick={() => onTypeChange('VOLUME')}>VOLUME</button>
				<span>Current: {activeType}</span>
			</div>
		),
);
jest.mock('../../components/stock/table-header', () => () => (
	<div data-testid='table-header' />
));
jest.mock('../../components/stock/stock-item', () => ({ data }: any) => (
	<div data-testid='stock-item'>{data.name}</div>
));

describe('RankLayout Component', () => {
	// 테스트용 가짜 주식 데이터
	const mockStockList = [
		{ id: '1', name: '삼성전자' },
		{ id: '2', name: 'SK하이닉스' },
	];

	beforeEach(() => {
		// 각 테스트 실행 전 커스텀 훅의 반환값을 초기화합니다.
		(useStockRankLogic as jest.Mock).mockReturnValue({
			stockList: mockStockList,
			sortType: 'value',
			isConnected: true,
		});
	});

	it('초기 렌더링 시 구성 요소들이 모두 표시되어야 한다', () => {
		/**
		 * @Given
		 * - useStockRankLogic 훅이 mockStockList(2개)를 반환하도록 설정됨
		 */

		/**
		 * @When
		 * - RankLayout 컴포넌트를 렌더링함
		 */
		render(<RankLayout />);

		/**
		 * @Then
		 * - 필터 그룹, 테이블 헤더가 화면에 존재하는지 확인
		 * - 렌더링된 주식 아이템(stock-item)의 개수가 2개인지 확인
		 */
		expect(screen.getByTestId('filter-group')).toBeInTheDocument();
		expect(screen.getByTestId('table-header')).toBeInTheDocument();
		expect(screen.getAllByTestId('stock-item')).toHaveLength(2);
	});

	it('초기 상태는 VALUE 타입으로 훅을 호출해야 한다', () => {
		/**
		 * @Given
		 * - 특별한 설정 없이 컴포넌트 준비
		 */

		/**
		 * @When
		 * - RankLayout 컴포넌트를 렌더링함
		 */
		render(<RankLayout />);

		/**
		 * @Then
		 * - 커스텀 훅(useStockRankLogic)이 'VALUE' 인자와 함께 호출되었는지 확인
		 * - 화면에 현재 상태가 'VALUE'로 표시되는지 확인
		 */
		expect(useStockRankLogic).toHaveBeenCalledWith('VALUE');
		expect(screen.getByText('Current: VALUE')).toBeInTheDocument();
	});

	it('필터 변경 시 훅이 새로운 타입으로 호출되어야 한다', () => {
		/**
		 * @Given
		 * - RankLayout 컴포넌트가 렌더링된 상태
		 */
		render(<RankLayout />);

		/**
		 * @When
		 * - 사용자가 'VOLUME' 버튼을 클릭하여 필터를 변경함
		 */
		fireEvent.click(screen.getByText('VOLUME'));

		/**
		 * @Then
		 * - 커스텀 훅이 변경된 인자인 'VOLUME'과 함께 다시 호출되었는지 확인
		 */
		expect(useStockRankLogic).toHaveBeenCalledWith('VOLUME');
	});
});
