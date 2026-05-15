import { useParams } from 'react-router-dom';
import { useOrderbook } from '../../hooks/stock-detail/use-orderbook';
import { OrderbookTable } from './orderbook-table';
import { useViewport } from '../../hooks/common/use-viewport';

export default function OrderbookSection() {
	const { id: stockCode = '' } = useParams<{ id: string }>();
	const { viewModel, status } = useOrderbook(stockCode);
	const viewport = useViewport();

	return (
		<OrderbookTable
			status={status}
			viewport={viewport}
			asks={viewModel?.asks}
			bids={viewModel?.bids}
			marketInfo={{
				weekHigh: 0,
				weekLow: 0,
				upperLimit: 0,
				lowerLimit: 0,
				open: 0,
				high: 0,
				low: 0,
				volume: 0,
				volumeUnit: '',
				changeFromYesterday: 0,
			}}
			onRetry={() => window.location.reload()}
		/>
	);
}