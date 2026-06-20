import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: Vite serves the client on :5173 and proxies /api to the Express token
// server on :8787, so the client can use the relative URL "/api/token".
// Prod: `vite build` outputs dist/, which the Express server also serves.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8787',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
