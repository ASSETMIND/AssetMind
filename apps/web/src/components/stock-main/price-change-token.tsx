import { useEffect, useRef, useState } from 'react';

type PriceChangeVariant = 'rise' | 'fall' | 'flat';

interface PriceChangeTokenProps {
	value: number;
	showSign?: boolean;
	animated?: boolean;
	className?: string;
}

function getVariant(value: number): PriceChangeVariant {
	if (value > 0) return 'rise';
	if (value < 0) return 'fall';
	return 'flat';
}

const textColorMap: Record<PriceChangeVariant, string> = {
	rise: '#EA580C',
	fall: '#256AF4',
	flat: '#9194A1',
};

const signMap: Record<PriceChangeVariant, string> = {
	rise: '+',
	fall: '',
	flat: '',
};

export const PriceChangeToken = ({
	value,
	showSign = true,
	animated = false,
	className,
}: PriceChangeTokenProps) => {
	const variant = getVariant(value);
	const sign = showSign ? signMap[variant] : '';
	const formatted = `${sign}${value.toFixed(2)}%`;

	const [displayValue, setDisplayValue] = useState(formatted);
	const [isAnimating, setIsAnimating] = useState(false);
	const prevValueRef = useRef(value);

	useEffect(() => {
		if (!animated) {
			setDisplayValue(formatted);
			return;
		}
		if (prevValueRef.current !== value) {
			setIsAnimating(true);
			const timer = setTimeout(() => {
				setDisplayValue(formatted);
				setIsAnimating(false);
			}, 150);
			prevValueRef.current = value;
			return () => clearTimeout(timer);
		}
	}, [value, formatted, animated]);

	return (
		<span
			style={{
				display: 'inline-block',
				overflow: 'hidden',
				fontSize: '15px',
				fontWeight: 500,
				fontVariantNumeric: 'tabular-nums',
				color: textColorMap[variant],
			}}
			className={className}
			aria-label={`등락률 ${formatted}`}
			aria-live='polite'
		>
			<span
				style={{
					display: 'inline-block',
					transition: 'transform 150ms, opacity 150ms',
					transform: isAnimating ? 'translateY(-100%)' : 'translateY(0)',
					opacity: isAnimating ? 0 : 1,
				}}
			>
				{displayValue}
			</span>
		</span>
	);
};

export default PriceChangeToken;