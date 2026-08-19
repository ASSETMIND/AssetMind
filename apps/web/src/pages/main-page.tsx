import RankLayout from '../components/stock-main/rank-layout';
import AdBanner from '../components/common/ad-banner';

export default function MainPage() {
	return (
		<div className='py-10'>
			<div className='py-5' />
			<AdBanner />
			<RankLayout />
		</div>
	);
}