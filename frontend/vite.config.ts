import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// HMR-only dev server; the built console is served by the backend on :8080.
const apiTarget = 'http://127.0.0.1:8080';

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2020',
    // Keep the React runtime in its own long-cached chunk; page chunks
    // (React.lazy in App.tsx) then only change when their page changes.
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) return 'vendor';
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/health': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
