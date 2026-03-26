import { render, screen, fireEvent, act } from '@testing-library/react';
import RankLayout from '../../components/stock-main/rank-layout';
import { useLatestSurgeAlert } from '../../hooks/stock/use-stock-alerts';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';

jest.mock('../../api/stock', () => ({
	STOCK_WS_URL: 'ws://localhost:8080/ws-stock',
	SURGE_ALERTS_TOPIC: '/topic/surge-alerts',
	getStockRanking: jest.fn(),
}));

// 1. 의존성 훅 및 하위 컴포넌트 모킹 (테스트 격리)
jest.mock('../../hooks/stock/use-stock-alerts');
jest.mock('../../hooks/stock/use-stock-rank-logic');

// Portal 및 자식 컴포넌트 렌더링 간소화
jest.mock(
	'../../components/common/portal',
	() =>
		({ children }: { children: React.ReactNode }) => <>{children}</>,
);
jest.mock('../../components/stock/stock-item', () => () => (
	<div data-testid='stock-item' />
));
jest.mock('../../components/stock/stock-filter-group', () => () => (
	<div data-testid='stock-filter-group' />
));
jest.mock('../../components/stock/table-header', () => () => (
	<div data-testid='table-header' />
));

describe('RankLayout - 급등락 알림 토스트 상호작용 및 시각화 테스트', () => {
	const mockClearAlert = jest.fn();

	beforeEach(() => {
		jest.clearAllMocks();

		// 랭킹 리스트 데이터 기본 모킹 (렌더링 오류 방지)
		(useStockRankLogic as jest.Mock).mockReturnValue({
			stockList: [],
			sortType: 'VALUE',
		});

		// 자동 닫힘(setTimeout) 상호작용 테스트를 위한 가짜 타이머
		jest.useFakeTimers();
	});

	afterEach(() => {
		act(() => {
			jest.runOnlyPendingTimers();
		});
		jest.useRealTimers();
	});

	it('수신된 최신 급등락 알림이 없을 경우 토스트가 렌더링되지 않아야 한다', () => {
		(useLatestSurgeAlert as jest.Mock).mockReturnValue({
			latestAlert: null,
			clearAlert: mockClearAlert,
		});

		render(<RankLayout />);

		expect(screen.queryByText('실시간 급등락 포착')).not.toBeInTheDocument();
	});

	it('급상승(양수) 알림 수신 시 빨간색 등락률과 함께 토스트가 렌더링되어야 한다', () => {
		(useLatestSurgeAlert as jest.Mock).mockReturnValue({
			latestAlert: {
				stockName: '삼성전자',
				changeRate: '+5.50%',
			},
			clearAlert: mockClearAlert,
		});

		render(<RankLayout />);

		// 텍스트 검증
		expect(screen.getByText('실시간 급등락 포착')).toBeInTheDocument();
		expect(screen.getByText('삼성전자')).toBeInTheDocument();

		// 색상 클래스 검증
		const rateText = screen.getByText('+5.50%');
		expect(rateText).toBeInTheDocument();
		expect(rateText).toHaveClass('text-red-500');
	});

	it('급하락(음수) 알림 수신 시 파란색 등락률과 함께 토스트가 렌더링되어야 한다', () => {
		(useLatestSurgeAlert as jest.Mock).mockReturnValue({
			latestAlert: {
				stockName: '카카오',
				changeRate: '-3.20%',
			},
			clearAlert: mockClearAlert,
		});

		render(<RankLayout />);

		const rateText = screen.getByText('-3.20%');
		expect(rateText).toBeInTheDocument();
		expect(rateText).toHaveClass('text-blue-500');
	});

	it('토스트의 닫기 버튼을 클릭하면 상태 초기화(clearAlert) 함수가 호출되어야 한다', () => {
		(useLatestSurgeAlert as jest.Mock).mockReturnValue({
			latestAlert: { stockName: 'SK하이닉스', changeRate: '+10.00%' },
			clearAlert: mockClearAlert,
		});

		render(<RankLayout />);

		// 닫기 상호작용
		const closeButton = screen.getByRole('button', { name: '닫기' });
		fireEvent.click(closeButton);

		const toastContainer = screen
			.getByText('실시간 급등락 포착')
			.closest('.pointer-events-auto');
		fireEvent.transitionEnd(toastContainer!); // 애니메이션 종료 이벤트 발생

		expect(mockClearAlert).toHaveBeenCalledTimes(1);
	});

	it('설정된 시간(2.5초)이 지나면 자동으로 닫히며 clearAlert 함수가 호출되어야 한다', () => {
		(useLatestSurgeAlert as jest.Mock).mockReturnValue({
			latestAlert: { stockName: '현대차', changeRate: '+2.00%' },
			clearAlert: mockClearAlert,
		});

		render(<RankLayout />);

		act(() => jest.advanceTimersByTime(2500));
		const toastContainer = screen
			.getByText('실시간 급등락 포착')
			.closest('.pointer-events-auto');
		fireEvent.transitionEnd(toastContainer!);

		expect(mockClearAlert).toHaveBeenCalledTimes(1);
	});
});
