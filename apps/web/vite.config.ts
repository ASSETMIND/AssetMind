import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [tailwindcss()],
	define: {
		global: 'window',
	},
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8080',
				changeOrigin: true,
			},
			'/ws-stock': {
				target: 'http://localhost:8080',
				changeOrigin: true,
				ws: true,
			},
		},
	},
});
