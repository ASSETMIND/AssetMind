import { twMerge } from 'tailwind-merge';

export type ButtonSize = 'sm' | 'md' | 'lg';

type Props = React.ComponentPropsWithoutRef<'button'> & {
	size?: ButtonSize;
};

export default function Button(props: Props) {
	const { className, children, size = 'md', ...rest } = props;

	return (
		<button
			className={twMerge(
				'flex w-full items-center justify-center font-medium',
				'bg-btn-primary hover:bg-btn-hover',
				'disabled:cursor-not-allowed disabled:bg-btn-disabled disabled:text-text-sub',
				getButtonSizeStyle(size),
				className
			)}
			{...rest}
		>
			{children}
		</button>
	);
}

function getButtonSizeStyle(size: ButtonSize) {
	switch (size) {
		case 'sm':
			return 'h-9 rounded-md px-3 text-sm';
		case 'md':
			return 'h-11 rounded-lg px-4 text-base';
		case 'lg':
			return 'h-14 rounded-xl px-6 text-lg';
		default:
			throw new Error(`Unsupported type size: ${size}`);
	}
}
