import { type ForwardedRef, forwardRef } from 'react';
import { twMerge } from 'tailwind-merge';

// 다음의 타입 정의
type Props = Omit<React.ComponentPropsWithRef<'input'>, 'type'> & {
	type: 'text' | 'password' | 'email' | 'search' | 'tel';
};

/*
	기본 Input 컴포넌트
	tailwind-merge를 사용하여 외부 스타일 주입을 가능하게 함
	forwardRef를 통해 부모 컴포넌트에서 돔 제어를 가능하게 함
 */

const Input = forwardRef(
	(props: Props, ref: ForwardedRef<HTMLInputElement>) => {
		const { className, ...rest } = props;

		return (
			<input
				ref={ref}
				className={twMerge(
					'h-12 w-full px-4 text-sm font-medium',
					'border outline-none',
					className
				)}
				{...rest}
			/>
		);
	}
);

Input.displayName = 'Input';
export default Input;
