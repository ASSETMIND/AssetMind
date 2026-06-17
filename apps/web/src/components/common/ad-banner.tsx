import { useEffect, useState } from 'react';
import { useViewport } from '../../hooks/common/use-viewport';

// 광고 배너 데이터 — 이미지 추가 시 여기에 넣으면 됨
const ADS = [
	{ imageUrl: '/src/assets/ad/desktop/ad-banner-1.png', mobileImageUrl: '/src/assets/ad/mobile/ad-banner-1.png', linkUrl: '#', alt: '광고 1' },
	{ imageUrl: '/src/assets/ad/desktop/ad-banner-2.png', mobileImageUrl: '/src/assets/ad/mobile/ad-banner-2.png', linkUrl: '#', alt: '광고 2' },
	{ imageUrl: '/src/assets/ad/desktop/ad-banner-3.png', mobileImageUrl: '/src/assets/ad/mobile/ad-banner-3.png', linkUrl: '#', alt: '광고 3' },
];

// 전환 간격 (ms) — 90초
const SLIDE_INTERVAL = 90_000;

// 구글 광고 표준 규격
// Desktop·Tablet : 728 x 90  (Leaderboard)
// Mobile         : 320 x 50  (Mobile Banner)

export default function AdBanner() {
	const viewport = useViewport();
	const isMobile = viewport === 'mobile';

	const [currentIndex, setCurrentIndex] = useState(0);

	// 일정 간격마다 다음 광고로 전환
	useEffect(() => {
		const timer = setInterval(() => {
			setCurrentIndex((prev) => (prev + 1) % ADS.length);
		}, SLIDE_INTERVAL);

		return () => clearInterval(timer);
	}, []);

	const ad = ADS[currentIndex];
	const src = isMobile ? ad.mobileImageUrl : ad.imageUrl;
	const width  = isMobile ? 320 : 728;
	const height = isMobile ? 50  : 90;

	const handleClick = () => {
		if (ad.linkUrl && ad.linkUrl !== '#') {
			window.open(ad.linkUrl, '_blank', 'noopener,noreferrer');
		}
	};

	return (
		<div
			style={{
				display:        'flex',
				justifyContent: 'center',
				width:          '100%',
				padding:        isMobile ? '8px 0' : '12px 0',
			}}
		>
			<div
				onClick={handleClick}
				role='button'
				aria-label={ad.alt}
				style={{
					width:           `${width}px`,
					height:          `${height}px`,
					cursor:          ad.linkUrl !== '#' ? 'pointer' : 'default',
					borderRadius:    '4px',
					overflow:        'hidden',
					flexShrink:      0,
					backgroundColor: '#21242C',
					// 전환 시 부드럽게 페이드
					transition:      'opacity 0.4s ease',
				}}
			>
				<img
					src={src}
					alt={ad.alt}
					style={{
						width:     '100%',
						height:    '100%',
						objectFit: 'cover',
						display:   'block',
					}}
					draggable={false}
				/>
			</div>
		</div>
	);
}
