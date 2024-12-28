import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {  // Match all API calls starting with "/api"
        target: 'http://localhost:8000', // Backend server URL
        changeOrigin: true,              // Handle cross-origin issues
        rewrite: (path) => path.replace(/^\/api/, ''), // Remove "/api" prefix before forwarding
      },
    },
  },
  css: {
    postcss: './postcss.config.js',
  },
});
