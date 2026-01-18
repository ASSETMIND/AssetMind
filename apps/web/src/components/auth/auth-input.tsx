import { type ForwardedRef, forwardRef, useState } from 'react';
import EyeOffIcon from '../icon/eye-off';
import EyeOnIcon from '../icon/eye-on';
import Input from '../common/input';

type AuthInputType = 'text' | 'password' | 'email';

type Props = Omit<React.ComponentPropsWithRef<'input'>, 'type'> & {
	type: AuthInputType;
	enablePasswordToggle?: boolean;
	label?: string;
	errorMessage?: string;
};

const AuthInput = forwardRef(
	(props: Props, ref: ForwardedRef<HTMLInputElement>) => {
		const {
			className,
			type,
			enablePasswordToggle = true,
			label,
			errorMessage,
			...rest
		} = props;

		const [isPasswordVisible, setIsPasswordVisible] = useState(false);

		const isPasswordType = type === 'password';
		const showToggleBtn = isPasswordType && enablePasswordToggle;
		const currentType = isPasswordType
			? isPasswordVisible
				? 'text'
				: 'password'
			: type;

		return (
			<div className='flex flex-col gap-1 w-full relative'>
				{label && <label className='font-medium'>{label}</label>}

				<div className='relative w-full'>
					<Input
						ref={ref}
						type={currentType}
						className={`
              w-full pr-10 transition-colors 
              ${errorMessage ? 'border-red-500 focus:ring-red-500' : ''}
              ${className}
            `}
						{...rest}
					/>

					{showToggleBtn && (
						<button
							type='button'
							onClick={() => setIsPasswordVisible(!isPasswordVisible)}
							className='absolute right-3 top-1/2 -translate-y-1/2 text-gray-500'
							tabIndex={-1}
						>
							{isPasswordVisible ? <EyeOnIcon /> : <EyeOffIcon />}
						</button>
					)}
				</div>
				{errorMessage && (
					<p className='absolute -bottom-5 left-1 text-xs text-red-500 font-medium animate-fadeIn'>
						{errorMessage}
					</p>
				)}
			</div>
		);
	},
);

AuthInput.displayName = 'AuthInput';
export default AuthInput;
