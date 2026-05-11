import { useState, useEffect } from 'react';

export type Viewport = 'desktop' | 'tablet' | 'mobile';

function getViewport(): Viewport {
	const w = window.innerWidth;
	if (w >= 1024) return 'desktop';
	if (w >= 768)  return 'tablet';
	return 'mobile';
}

export function useViewport(): Viewport {
	const [viewport, setViewport] = useState<Viewport>(getViewport);

	useEffect(() => {
		const handler = () => setViewport(getViewport());
		window.addEventListener('resize', handler);
		return () => window.removeEventListener('resize', handler);
	}, []);

	return viewport;
}