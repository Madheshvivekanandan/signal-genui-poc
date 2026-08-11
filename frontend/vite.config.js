import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The backend port is configurable because 8000 is a busy default — another local
// stack holding it makes the dev server proxy to a different app entirely, which
// looks like a bug in this one. Set BACKEND_URL to override.
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Same-origin in dev, so the SSE endpoints need no CORS preflight and the
      // frontend code carries no notion of a backend host.
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
});
