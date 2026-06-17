import RankLayout from '../components/stock-main/rank-layout';
import AdBanner from '../components/common/ad-banner';

export default function MainPage() {
	return (
		<div className='py-10'>
			<div className='py-24' />
			{/* 상단 광고 배너 — 이미지 준비 후 imageUrl, linkUrl props 교체 */}
			<AdBanner />
			<RankLayout />
		</div>
	);
}
