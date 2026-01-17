import { twMerge } from 'tailwind-merge';

// 버튼 사이즈 정의
export type ButtonSize = 'sm' | 'md' | 'lg';

// ComponentPropsWithoutRef를 사용해 자유로운 커스터마이징 가능
type Props = React.ComponentPropsWithoutRef<'button'> & {
	size?: ButtonSize;
};

/*
	className을 통해 추가적인 스타일 오버라이딩을 허용
	size 속성을 통해 사전 정의된 크기 스타일을 적용
*/
export default function Button(props: Props) {
	// 기본사이즈 md
	const { className, children, size = 'md', ...rest } = props;

	return (
		<button
			className={twMerge(
				'flex w-full items-center justify-center font-medium border',
				getButtonSizeStyle(size),
				className
			)}
			{...rest}
		>
			{children}
		</button>
	);
}

// 사이즈 정의에 대한 함수
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
