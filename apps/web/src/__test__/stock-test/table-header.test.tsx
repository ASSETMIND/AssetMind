import { render, screen } from '@testing-library/react';
import TableHeader from '../../components/stock-main/table-header';

describe('TableHeader Component', () => {
	it('기본적으로 모든 헤더 컬럼이 렌더링되어야 한다', () => {
		/**
		 * @Given
		 * - 별도의 인자 없이 컴포넌트 준비
		 */

		/**
		 * @When
		 * - TableHeader 컴포넌트를 렌더링
		 */
		render(<TableHeader />);

		/**
		 * @Then
		 * - 고정적으로 노출되어야 하는 컬럼명(순위, 현재가, 등락률 등)이 모두 존재하는지 확인
		 */
		expect(screen.getByText('순위')).toBeInTheDocument();
		expect(screen.getByText('현재가')).toBeInTheDocument();
		expect(screen.getByText('등락률')).toBeInTheDocument();
		expect(screen.getByText('증권 거래 비율 ⓘ')).toBeInTheDocument();
	});

	it('sortType이 "value"일 때 "거래대금순"으로 표시되어야 한다', () => {
		/**
		 * @Given
		 * - 정렬 타입(sortType)을 'value'로 설정
		 */
		const sortType = 'value';

		/**
		 * @When
		 * - 설정된 sortType과 함께 컴포넌트 렌더링
		 */
		render(<TableHeader sortType={sortType} />);

		/**
		 * @Then
		 * - 거래대금 기준으로 정렬되었음을 알리는 '거래대금순' 텍스트가 화면에 있는지 확인
		 */
		expect(screen.getByText('거래대금순')).toBeInTheDocument();
	});

	it('sortType이 "volume"일 때 "거래량순"으로 표시되어야 한다', () => {
		/**
		 * @Given
		 * - 정렬 타입(sortType)을 'volume'으로 설정
		 */
		const sortType = 'volume';

		/**
		 * @When
		 * - 설정된 sortType과 함께 컴포넌트 렌더링
		 */
		render(<TableHeader sortType={sortType} />);

		/**
		 * @Then
		 * - '거래량순' 텍스트는 존재해야 함
		 * - 반대로 '거래대금순' 텍스트는 화면에서 사라져야 함
		 */
		expect(screen.getByText('거래량순')).toBeInTheDocument();
		expect(screen.queryByText('거래대금순')).not.toBeInTheDocument();
	});
});
