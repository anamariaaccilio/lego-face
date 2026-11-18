import { defineConfig } from 'vite';

// En desarrollo, /api va al servidor de Python.
export default defineConfig({
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8765' },
  },
  build: { chunkSizeWarningLimit: 1200 },
});
