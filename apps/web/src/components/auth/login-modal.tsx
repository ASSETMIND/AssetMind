import Modal from '../common/modal';
import Button from '../common/button';
import AuthInput from '../auth/auth-input';
import GoogleIcon from '../icon/google';
import KakaoIcon from '../icon/kakao';

type Props = {
	onClose: () => void;
	onClickSignup: () => void;
	onClickFindIdPw: () => void;
};

export default function LoginModal({
	onClose,
	onClickSignup,
	onClickFindIdPw,
}: Props) {
	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col items-center'>
				<h2 className='text-4xl font-bold'>LOGIN</h2>
				<p className='mb-6'>AssetMind에 오신 것을 환영합니다.</p>
				<form className='w-full flex flex-col gap-8'>
					<div className='flex flex-col gap-4'>
						<label className=' font-medium'>아이디</label>
						<AuthInput type='email' placeholder='아이디를 입력해 주세요.' />
					</div>
					<div className='flex flex-col gap-4'>
						<label className='font-medium'>비밀번호</label>
						<AuthInput
							type='password'
							placeholder='비밀번호를 입력해 주세요.'
						/>
					</div>
					<Button className='mt-2' type='submit'>
						로그인
					</Button>
				</form>

				<div className='mt-4 flex gap-4 text-[#9194A1]'>
					<button className='cursor-pointer' onClick={onClickFindIdPw}>
						아이디/비밀번호 찾기
					</button>
					<p>|</p>
					<button className='cursor-pointer' onClick={onClickSignup}>
						회원가입
					</button>
				</div>
				<div className='mt-4 w-full'>
					<div className='relative flex w-full items-center justify-center'>
						<div className='absolute w-full border-t border-border-input'></div>
						<span className='relative bg-bg-modal px-3 font-bold text-text-sub'>
							or continue with
						</span>
					</div>

					<div className='mt-4 flex justify-center gap-8'>
						<button>
							<GoogleIcon />
						</button>

						<button>
							<KakaoIcon />
						</button>
					</div>
				</div>
			</div>
		</Modal>
	);
}
