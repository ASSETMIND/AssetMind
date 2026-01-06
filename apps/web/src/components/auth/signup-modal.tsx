import Modal from '../common/modal';
import Button from '../common/button';
import AuthInput from '../auth/auth-input';
import Input from '../common/input';

type Props = {
	onClose: () => void;
	onClickLogin: () => void;
};

export default function SignupModal({ onClose, onClickLogin }: Props) {
	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col w-full px-2'>
				<h2 className='mb-6 text-center text-4xl font-bold'>SIGN UP</h2>

				<form className='flex flex-col gap-8'>
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>아이디</label>
						<div className='relative'>
							<Input
								type='text'
								placeholder='영문 소문자, 숫자 포함 4~20자'
								className='pr-24'
							/>
							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-20 -translate-y-1/2 text-xs'
							>
								중복 확인
							</Button>
						</div>
					</div>

					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호</label>
						<AuthInput
							type='password'
							placeholder='영문, 숫자, 특수문자 포함 8자 이상'
						/>
					</div>

					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호 확인</label>
						<AuthInput
							type='password'
							placeholder='비밀번호를 한 번 더 입력해 주세요.'
						/>
					</div>

					<div className='flex flex-col gap-2'>
						<label className='font-medium'>휴대폰 번호</label>

						<div className='relative'>
							<Input type='tel' placeholder='010-0000-0000' className='pr-28' />
							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-24 -translate-y-1/2 text-xs'
							>
								인증번호 전송
							</Button>
						</div>

						<div className='relative'>
							<Input
								type='text'
								placeholder='인증번호 입력'
								className='pr-24'
							/>
							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-20 -translate-y-1/2 text-xs'
							>
								인증 확인
							</Button>
						</div>
					</div>

					<Button type='submit' size='lg' className='w-full'>
						가입하기
					</Button>
				</form>

				<div className='mt-4 flex gap-4 items-center justify-center'>
					<p>이미 게정이 있으신가요?</p>
					<button
						className='cursor-pointer font-semibold'
						onClick={onClickLogin}
					>
						로그인
					</button>
				</div>
			</div>
		</Modal>
	);
}
