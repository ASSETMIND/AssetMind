import reactDom from 'react-dom';

type PortalType = 'modal' | 'toast';

type Props = {
	children: React.ReactNode;
	type?: PortalType;
};

export default function Portal({ children, type = 'modal' }: Props) {
	const rootId = type === 'toast' ? 'toast-root' : 'modal-root';
	const element = document.getElementById(rootId) as HTMLElement;

	return reactDom.createPortal(children, element);
}
