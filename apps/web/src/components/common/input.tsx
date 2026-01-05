import { type ForwardedRef, forwardRef } from 'react';
import { twMerge } from 'tailwind-merge';

type Props = Omit<React.ComponentPropsWithRef<'input'>, 'type'> & {
	type: 'text' | 'password' | 'email' | 'search' | 'tel';
};

const Input = forwardRef(
	(props: Props, ref: ForwardedRef<HTMLInputElement>) => {
		const { className, ...rest } = props;

		return (
			<input
				ref={ref}
				className={twMerge(
					'h-12 w-full rounded-lg px-4 text-sm font-medium transition-colors',
					'bg-bg-input placeholder-text-placeholder',
					'border border-border-input outline-none',
					className
				)}
				{...rest}
			/>
		);
	}
);

Input.displayName = 'Input';
export default Input;
