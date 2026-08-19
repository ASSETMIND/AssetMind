import { useEffect, useRef, useState } from 'react';

export interface MobileTabItem {
	label: string;
	value: string;
	icon: React.ReactNode;
}

interface MobileTabSwitcherProps {
	items: MobileTabItem[];
	defaultValue?: string;
	value?: string;
	onChange?: (value: string) => void;
	className?: string;
}

export const MobileTabSwitcher = ({
	items,
	defaultValue,
	value: controlledValue,
	onChange,
	className,
}: MobileTabSwitcherProps) => {
	const [internalValue, setInternalValue] = useState(
		defaultValue ?? items[0]?.value,
	);
	const [isSticky, setIsSticky] = useState(false);
	const sentinelRef = useRef<HTMLDivElement>(null);

	const activeValue = controlledValue ?? internalValue;

	const handleClick = (val: string) => {
		if (!controlledValue) setInternalValue(val);
		onChange?.(val);
	};

	useEffect(() => {
		const sentinel = sentinelRef.current;
		if (!sentinel) return;

		const observer = new IntersectionObserver(
			([entry]) => setIsSticky(!entry.isIntersecting),
			{ threshold: 0, rootMargin: '0px' },
		);

		observer.observe(sentinel);
		return () => observer.disconnect();
	}, []);

	return (
		<>
			<div
				className={className}
				role='tablist'
				aria-orientation='horizontal'
				style={{
					position: 'sticky',
					bottom: 0,
					zIndex: 50,
					width: '100%',
					backgroundColor: '#131316',
					borderRadius: '20px 20px 0 0',
					border: '1px solid #252525',
					boxShadow: isSticky ? '0 -2px 12px rgba(0,0,0,0.4)' : 'none',
					transition: 'box-shadow 200ms',
				}}
			>
				<div style={{
					width: '100%',
					height: '64px',
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'space-between',
					padding: '10px 40px',
					boxSizing: 'border-box',
				}}>
					{items.map((item) => {
						const isActive = activeValue === item.value;
						return (
							<button
								key={item.value}
								role='tab'
								aria-selected={isActive}
								tabIndex={isActive ? 0 : -1}
								onClick={() => handleClick(item.value)}
								style={{
									display: 'flex',
									flexDirection: 'column',
									alignItems: 'center',
									gap: '6px',
									background: 'none',
									border: 'none',
									cursor: 'pointer',
									color: isActive ? '#FFFFFF' : '#9F9F9F',
									opacity: isActive ? 1 : 0.7,
									transition: 'color 150ms, opacity 150ms',
									padding: 0,
								}}
							>
								<span style={{ width: '24px', height: '24px', display: 'flex', alignItems: 'center', justifyContent: 'center' }} aria-hidden='true'>
									{item.icon}
								</span>
								<span style={{ fontSize: '12px', fontWeight: 700, lineHeight: 1 }}>
									{item.label}
								</span>
							</button>
						);
					})}
				</div>
			</div>

			{/* Sticky 감지용 sentinel */}
			<div ref={sentinelRef} style={{ height: 0 }} aria-hidden='true' />
		</>
	);
};

export default MobileTabSwitcher;