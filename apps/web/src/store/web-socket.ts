import { create } from 'zustand';

interface WebSocketState {
	isConnected: boolean;
	lastMessage: MessageEvent | null;
	error: Event | null;
	setIsConnected: (isConnected: boolean) => void;
	setLastMessage: (message: MessageEvent | null) => void;
	setError: (error: Event | null) => void;
}

export const useWebSocketStore = create<WebSocketState>((set) => ({
	isConnected: false,
	lastMessage: null,
	error: null,
	setIsConnected: (isConnected) => set({ isConnected }),
	setLastMessage: (lastMessage) => set({ lastMessage }),
	setError: (error) => set({ error }),
}));
