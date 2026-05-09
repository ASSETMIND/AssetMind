import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
	children: ReactNode;
	fallback?: ReactNode;
}

interface State {
	hasError: boolean;
	error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
	constructor(props: Props) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error): State {
		return { hasError: true, error };
	}

	componentDidCatch(error: Error, info: ErrorInfo) {
		console.error('[ErrorBoundary]', error, info);
	}

	handleReset = () => {
		this.setState({ hasError: false, error: null });
	};

	render() {
		if (this.state.hasError) {
			if (this.props.fallback) return this.props.fallback;

			return (
				<div
					style={{
						display: 'flex',
						flexDirection: 'column',
						alignItems: 'center',
						justifyContent: 'center',
						minHeight: '400px',
						gap: '16px',
						color: '#9194A1',
					}}
				>
					<svg width='40' height='40' viewBox='0 0 24 24' fill='none'>
						<path
							d='M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z'
							stroke='#9194A1'
							strokeWidth='2'
							strokeLinecap='round'
							strokeLinejoin='round'
						/>
					</svg>
					<p style={{ fontSize: '14px', textAlign: 'center', margin: 0 }}>
						예상치 못한 오류가 발생했습니다.
					</p>
					{this.state.error && (
						<p style={{ fontSize: '12px', color: '#4B4B50', textAlign: 'center', margin: 0 }}>
							{this.state.error.message}
						</p>
					)}
					<button
						onClick={this.handleReset}
						style={{
							padding: '8px 20px',
							backgroundColor: '#6B4EFF',
							border: 'none',
							borderRadius: '8px',
							color: '#FFFFFF',
							fontSize: '14px',
							cursor: 'pointer',
						}}
					>
						다시 시도
					</button>
				</div>
			);
		}

		return this.props.children;
	}
}

export default ErrorBoundary;