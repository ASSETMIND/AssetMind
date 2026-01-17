import googleIcon from '../../assets/images/google.svg';

export default function GoogleIcon() {
	return (
		<div className='bg-white flex w-15 h-15 rounded-full items-center  justify-center'>
			<img src={googleIcon} alt='google' width={45} height={45} />
		</div>
	);
}
