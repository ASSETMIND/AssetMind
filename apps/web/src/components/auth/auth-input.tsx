import { type ForwardedRef, forwardRef, useState } from 'react';
import EyeOffIcon from '../icon/eye-off';
import EyeOnIcon from '../icon/eye-on';
import Input from '../common/input';

// 안증인풋 관련정의
type AuthInputType = 'text' | 'password' | 'email';

// 기본 인풋 타입을 상속받지만 타입 속성은 인증 인풋으로 제한함
// 비밀번호 토글을 옵셔널로 정의
// Omit: 기본 인풋의 타입 정의를 제거하여 충돌 방지 및 타입 안전성 확보

type Props = Omit<React.ComponentPropsWithRef<'input'>, 'type'> & {
	type: AuthInputType;
	enablePasswordToggle?: boolean;
	label?: string;
	errorMessage?: string;
};

/*
	인증(로그인, 회원가입) 과정에서 사용되는 확장된 Input 컴포넌트
	다른 라이브러리와 연동을 위해 forwardRef로 구성
*/
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

		// 타입이 패스워드면 토글버튼 띄움
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
