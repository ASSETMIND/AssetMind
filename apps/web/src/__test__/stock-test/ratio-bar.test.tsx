import { render, screen } from '@testing-library/react';
import RatioBar from '../../components/stock/ratio-bar';

describe('RatioBar Component', () => {
	it('매수(buy)와 매도(sell) 수치가 텍스트로 표시되어야 한다', () => {
		/**
		 * @Given
		 * - 매수 비중 60, 매도 비중 40이라는 데이터를 준비
		 */
		const buyValue = 60;
		const sellValue = 40;

		/**
		 * @When
		 * - RatioBar 컴포넌트에 해당 데이터를 넣어 렌더링함
		 */
		render(<RatioBar buy={buyValue} sell={sellValue} />);

		/**
		 * @Then
		 * - 화면에 '60'과 '40'이라는 텍스트가 정상적으로 나타나는지 확인
		 */
		expect(screen.getByText('60')).toBeInTheDocument();
		expect(screen.getByText('40')).toBeInTheDocument();
	});

	it('비율에 맞는 width 스타일이 적용되어야 한다', () => {
		/**
		 * @Given
		 * - 매수 70%, 매도 30%라는 비중 데이터를 설정
		 */
		const buyPercent = 70;
		const sellPercent = 30;

		/**
		 * @When
		 * - 컴포넌트를 렌더링하고 스타일 검사를 위해 DOM 컨테이너를 가져옴
		 */
		const { container } = render(
			<RatioBar buy={buyPercent} sell={sellPercent} />,
		);

		/**
		 * @Then
		 * - 바 그래프를 구성하는 두 개의 div 요소를 찾음
		 * - 첫 번째 바(매수)의 너비가 '70%'인지 확인
		 * - 두 번째 바(매도)의 너비가 '30%'인지 확인
		 */
		const bars = container.querySelectorAll('.h-1\\.5 > div');

		expect(bars).toHaveLength(2);
		expect(bars[0]).toHaveStyle({ width: `${buyPercent}%` });
		expect(bars[1]).toHaveStyle({ width: `${sellPercent}%` });
	});
});
