import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { twMerge } from 'tailwind-merge';

type InputState = 'default' | 'error' | 'success';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
	label?: string;
	error?: string;
	message?: string;
	state?: InputState;
	icon?: ReactNode;
	onIconClick?: () => void;
	rightSection?: ReactNode;
	rightSectionWidth?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(({
	className,
	label,
	error,
	message,
	state = 'default',
	icon,
	onIconClick,
	rightSection,
	rightSectionWidth = 'pr-[50px]',
	id,
	...props
}, ref) => {

	const finalState = error ? 'error' : state;
	const finalMessage = error || message;

	// focus 테두리: 흰색(#FFFFFF), 에러: #EC1A13, 성공: #256AF4
	const stateStyles: Record<InputState, string> = {
		default: 'border-[#383A42] focus:border-[#FFFFFF]',
		error:   'border-[#EC1A13] focus:border-[#EC1A13]',
		success: 'border-[#256AF4] focus:border-[#256AF4]',
	};

	return (
		<div className='w-full flex flex-col gap-2'>
			{label && (
				<label htmlFor={id} style={{ fontSize: '16px', fontWeight: 400, color: '#FFFFFF' }}>
					{label}
				</label>
			)}

			<div className='relative'>
				<input
					ref={ref}
					id={id}
					className={twMerge(
						'w-full h-[57px] px-[25px] rounded-lg border outline-none transition-all duration-200',
						'text-[14px] leading-[150%] font-normal',
						'text-white placeholder:text-[#808080]',
						'bg-[#1C1D21]',
						stateStyles[finalState],
						(icon || rightSection) && rightSectionWidth,
						className,
					)}
					{...props}
				/>

				{icon && !rightSection && (
					<button
						type='button'
						onClick={onIconClick}
						style={{ position: 'absolute', right: '20px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9194A1', display: 'flex', alignItems: 'center' }}
					>
						{icon}
					</button>
				)}

				{rightSection && (
					<div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)' }}>
						{rightSection}
					</div>
				)}
			</div>

			{finalMessage && (
				<p style={{
					fontSize: '12px',
					marginTop: '4px',
					color: finalState === 'error' ? '#EC1A13' : finalState === 'success' ? '#256AF4' : '#9194A1',
				}}>
					{finalMessage}
				</p>
			)}
		</div>
	);
});

Input.displayName = 'Input';
export default Input;