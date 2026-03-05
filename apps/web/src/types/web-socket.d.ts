export interface UseWebSocketReturn {
	isConnected: boolean;
	lastMessage: MessageEvent | null;
	error: Event | null;
	sendMessage: (message: string | ArrayBuffer | Blob) => void;
	connect: () => void;
	disconnect: () => void;
}
