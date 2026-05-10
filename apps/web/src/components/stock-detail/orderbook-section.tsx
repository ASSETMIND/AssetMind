import { useParams } from 'react-router-dom';
import { useOrderbook } from '../../hooks/stock-detail/use-orderbook';
import { OrderbookTable } from './orderbook-table';
import { useViewport } from '../../hooks/common/use-viewport';

export default function OrderbookSection() {
	const { id: stockCode = '' } = useParams<{ id: string }>();
	const { data, status } = useOrderbook(stockCode);
	const viewport = useViewport();

	return (
		<OrderbookTable
			status={status as any}
			viewport={viewport}
			currentPrice={data?.currentPrice}
			currentChangeRate={data?.currentChangeRate}
			asks={data?.asks}
			bids={data?.bids}
			trades={data?.trades?.map((t, i) => ({ ...t, id: `trade-${i}` }))}
			tradeStrength={data?.tradeStrength}
			marketInfo={data?.marketInfo}
			onRetry={() => window.location.reload()}
		/>
	);
}