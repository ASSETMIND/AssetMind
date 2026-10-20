import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [tailwindcss()],
	define: {
		global: 'window',
	},
	worker: {
		format: 'es',
	},
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:9090',
				changeOrigin: true,
			},
			'/ws-orderbook': {
				target: 'ws://localhost:9090',
				ws: true,
				changeOrigin: true,
				rewrite: () => '/ws-stock',
			},
		},
	},
});