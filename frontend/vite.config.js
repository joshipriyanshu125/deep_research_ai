import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Use IPv4 explicitly. On Windows, `localhost` may resolve to ::1
        // first while the API is listening on IPv4, which produces the
        // recurring internalConnectMultiple/ECONNREFUSED proxy error.
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
        timeout: 30000,
        proxyTimeout: 30000,
        configure: (proxy) => {
          proxy.on('error', (_error, _request, response) => {
            if (!response || response.headersSent) return;

            response.writeHead(503, { 'Content-Type': 'application/json' });
            response.end(JSON.stringify({
              success: false,
              message: 'Backend is starting. Please retry in a moment.',
            }));
          });
        },
      },
    },
  },
})
