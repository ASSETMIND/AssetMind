import { render, screen, fireEvent } from '@testing-library/react';
import StockFilterGroup from '../../components/stock/stock-filter-group';

describe('StockFilterGroup Component', () => {
	// Mock 함수 생성: 버튼 클릭 시 호출될 함수를 가짜로 만듭니다.
	const mockOnTypeChange = jest.fn();

	beforeEach(() => {
		// 각 테스트 시작 전 호출 기록을 초기화하여 독립성을 보장합니다.
		mockOnTypeChange.mockClear();
	});

	it('모든 필터 버튼들이 화면에 렌더링되어야 한다', () => {
		/**
		 * @Given
		 * - 'VALUE'가 활성화된 상태로 설정
		 */

		/**
		 * @When
		 * - StockFilterGroup 컴포넌트를 렌더링
		 */
		render(
			<StockFilterGroup activeType='VALUE' onTypeChange={mockOnTypeChange} />,
		);

		/**
		 * @Then
		 * - 기획서에 명시된 모든 버튼 텍스트가 화면에 존재하는지 확인
		 */
		expect(screen.getByText('전체')).toBeInTheDocument();
		expect(screen.getByText('국내')).toBeInTheDocument();
		expect(screen.getByText('거래대금순')).toBeInTheDocument();
		expect(screen.getByText('거래량순')).toBeInTheDocument();
		expect(screen.getByText('실시간')).toBeInTheDocument();
	});

	it('"거래대금순" 버튼 클릭 시 onTypeChange("VALUE")가 호출되어야 한다', () => {
		/**
		 * @Given
		 * - 현재 활성 타입이 'VOLUME'인 상태로 렌더링
		 */
		render(
			<StockFilterGroup activeType='VOLUME' onTypeChange={mockOnTypeChange} />,
		);

		/**
		 * @When
		 * - '거래대금순' 버튼을 찾아 클릭 이벤트 발생
		 */
		const button = screen.getByText('거래대금순');
		fireEvent.click(button);

		/**
		 * @Then
		 * - 콜백 함수(onTypeChange)가 정확히 1번 호출되었는지 확인
		 * - 호출 시 전달된 인자가 'VALUE'인지 확인
		 */
		expect(mockOnTypeChange).toHaveBeenCalledTimes(1);
		expect(mockOnTypeChange).toHaveBeenCalledWith('VALUE');
	});

	it('"거래량순" 버튼 클릭 시 onTypeChange("VOLUME")이 호출되어야 한다', () => {
		/**
		 * @Given
		 * - 현재 활성 타입이 'VALUE'인 상태로 렌더링
		 */
		render(
			<StockFilterGroup activeType='VALUE' onTypeChange={mockOnTypeChange} />,
		);

		/**
		 * @When
		 * - '거래량순' 버튼을 찾아 클릭 이벤트 발생
		 */
		const button = screen.getByText('거래량순');
		fireEvent.click(button);

		/**
		 * @Then
		 * - 콜백 함수가 정확히 1번 호출되었는지 확인
		 * - 호출 시 전달된 인자가 'VOLUME'인지 확인
		 */
		expect(mockOnTypeChange).toHaveBeenCalledTimes(1);
		expect(mockOnTypeChange).toHaveBeenCalledWith('VOLUME');
	});

	it('활성화된 탭(activeType)에 따라 스타일이 다르게 적용되어야 한다', () => {
		/**
		 * @Given
		 * - 'VALUE' 타입을 활성 상태로 설정하여 렌더링
		 */
		render(
			<StockFilterGroup activeType='VALUE' onTypeChange={mockOnTypeChange} />,
		);

		/**
		 * @When
		 * - 검증할 버튼 요소들(거래대금순, 거래량순)을 획득
		 */
		const valueBtn = screen.getByText('거래대금순');
		const volumeBtn = screen.getByText('거래량순');

		/**
		 * @Then
		 * - 활성화된 버튼(VALUE)은 강조 스타일('text-white')을 가졌는지 확인
		 * - 비활성화된 버튼(VOLUME)은 무채색 스타일('text-gray-400')을 가졌는지 확인
		 */
		expect(valueBtn).toHaveClass('text-white');
		expect(volumeBtn).toHaveClass('text-gray-400');
	});
});
