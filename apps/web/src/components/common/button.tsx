import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { twMerge } from 'tailwind-merge';

type ButtonVariant = 'primary' | 'secondary' | 'kakao' | 'google';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
	children: ReactNode;
	variant?: ButtonVariant;
	size?: ButtonSize;
	fullWidth?: boolean;
	isLoading?: boolean;
	loadingText?: string;
}

// Storybook tailwind.config.ts 기준
// button.large.primary = #131316 (어두운 검정) → size lg
// button.small.primary = #6D4AE6 (보라색) → size sm/md

const Button = forwardRef<HTMLButtonElement, ButtonProps>(({
	children,
	variant = 'primary',
	size = 'md',
	fullWidth = false,
	isLoading = false,
	loadingText = '로딩 중...',
	disabled,
	className,
	...props
}, ref) => {

	const baseStyles = 'inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 cursor-pointer';

	const getVariantStyle = () => {
		if (variant === 'primary') {
			if (size === 'lg') {
				// button.large.primary
				return 'bg-[#131316] text-white hover:bg-[#2C2C30]';
			}
			// button.small.primary
			return 'bg-[#6D4AE6] text-white hover:bg-[#5F3FD1]';
		}
		if (variant === 'secondary') return 'bg-[#21242C] text-white hover:bg-[#2C2C30]';
		if (variant === 'kakao')     return 'bg-[#FEE500] text-[#191919] hover:opacity-90';
		if (variant === 'google')    return 'bg-white border border-[#383A42] text-[#191919] hover:bg-gray-50';
		return '';
	};

	const sizes: Record<ButtonSize, string> = {
		sm:   'h-9 px-3 text-[14px]',
		md:   'h-[52px] px-6 text-[14px]',
		lg:   'h-[54px] px-8 text-[16px] w-full',
		icon: 'w-12 h-12 rounded-full p-0',
	};

	return (
		<button
			ref={ref}
			className={twMerge(
				baseStyles,
				getVariantStyle(),
				sizes[size],
				fullWidth ? 'w-full' : '',
				className,
			)}
			disabled={disabled || isLoading}
			{...props}
		>
			{isLoading ? (
				<>
					<svg className='animate-spin -ml-1 mr-2 h-4 w-4' xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' aria-hidden='true'>
						<circle className='opacity-25' cx='12' cy='12' r='10' stroke='currentColor' />
						<path className='opacity-75' fill='currentColor' d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z' />
					</svg>
					<span>{loadingText}</span>
				</>
			) : children}
		</button>
	);
});

Button.displayName = 'Button';
export default Button;