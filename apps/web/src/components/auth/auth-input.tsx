import { type ForwardedRef, forwardRef, useState } from 'react';
import EyeOffIcon from '../icon/eye-off';
import EyeOnIcon from '../icon/eye-on';
import Input from '../common/input';

type AuthInputType = 'text' | 'password' | 'email';

type Props = Omit<React.ComponentPropsWithRef<'input'>, 'type'> & {
	type: AuthInputType;
	enablePasswordToggle?: boolean;
};

const AuthInput = forwardRef(
	(props: Props, ref: ForwardedRef<HTMLInputElement>) => {
		const { className, type, enablePasswordToggle = true, ...rest } = props;
		const [isPasswordVisible, setIsPasswordVisible] = useState(false);

		const isPasswordType = type === 'password';
		const showToggleBtn = isPasswordType && enablePasswordToggle;

		const currentType = isPasswordType
			? isPasswordVisible
				? 'text'
				: 'password'
			: type;

		const handleToggle = () => {
			setIsPasswordVisible((prev) => !prev);
		};

		return (
			<div className='relative w-full'>
				<Input
					ref={ref}
					type={currentType}
					className={showToggleBtn ? 'pr-12' : ''}
					{...rest}
				/>

				{showToggleBtn && (
					<button
						type='button'
						onClick={handleToggle}
						className='absolute right-4 top-1/2 -translate-y-1/2'
						aria-label={isPasswordVisible ? '비밀번호 숨기기' : '비밀번호 보기'}
						tabIndex={-1}
					>
						{isPasswordVisible ? <EyeOnIcon /> : <EyeOffIcon />}
					</button>
				)}
			</div>
		);
	}
);

AuthInput.displayName = 'AuthInput';
export default AuthInput;
