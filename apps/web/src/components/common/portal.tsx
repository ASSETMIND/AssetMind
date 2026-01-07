import reactDom from 'react-dom';

type PortalType = 'modal' | 'toast';

type Props = {
	children: React.ReactNode;
	type?: PortalType;
};

/*
	React Portal 기능을 래핑하여 특정 돔 노드에 자식을 렌더링하는 컴포넌트
	부모 컴포넌트의 돔 계층 구조를 벗어나
	index.html에 미리 정의된 루트 요소(modal-root, toast-root)에 UI를 렌더링
	(z-index 관리 및 오버레이 처리에 용이)
 */
export default function Portal({ children, type = 'modal' }: Props) {
	const rootId = type === 'toast' ? 'toast-root' : 'modal-root';
	const element = document.getElementById(rootId) as HTMLElement;

	// 포탈을 속성들과 반환
	return reactDom.createPortal(children, element);
}
