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
};

/*
	인증(로그인, 회원가입) 과정에서 사용되는 확장된 Input 컴포넌트
	다른 라이브러리와 연동을 위해 forwardRef로 구성
*/
const AuthInput = forwardRef(
	(props: Props, ref: ForwardedRef<HTMLInputElement>) => {
		const { className, type, enablePasswordToggle = true, ...rest } = props;
		const [isPasswordVisible, setIsPasswordVisible] = useState(false);

		// 타입이 패스워드면 토글버튼 띄움
		const isPasswordType = type === 'password';
		const showToggleBtn = isPasswordType && enablePasswordToggle;

		/**
			실제 input 속성에 전달될 type 속성 결정
			비밀번호 타입이면서 사용자가 보기를 선택한 경우 -> 텍스트로 변경하여 내용을 보여줌
			그 외의 경우 -> 전달받은 type(email, text, password 등)을 그대로 유지
     */
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
				{/* 기본 인풋 활용 */}
				<Input
					ref={ref}
					type={currentType}
					className={showToggleBtn ? 'pr-12' : ''} // 토글 버튼 있을 때 공간확보
					{...rest}
				/>

				{/*
					조건부 렌더링을 통한 비밀번호 토글버튼
					겹쳐 표시하기위해 absolute 사용
					탭키로 이동 가능 다음 인풋 이동 가능
				*/}
				{showToggleBtn && (
					<button
						type='button'
						onClick={handleToggle}
						className='absolute right-4 top-1/2 -translate-y-1/2'
						aria-label={isPasswordVisible ? '비밀번호 숨기기' : '비밀번호 보기'}
						tabIndex={-1}
					>
						{/* 토글버튼 */}
						{isPasswordVisible ? <EyeOnIcon /> : <EyeOffIcon />}
					</button>
				)}
			</div>
		);
	}
);

AuthInput.displayName = 'AuthInput';
export default AuthInput;
