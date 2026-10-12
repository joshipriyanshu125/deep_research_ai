import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { spawn } from 'node:child_process';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function isPortOpen(port, host = '127.0.0.1', timeoutMs = 600) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let resolved = false;
    socket.setTimeout(timeoutMs);
    socket.on('connect', () => {
      resolved = true;
      socket.destroy();
      resolve(true);
    });
    socket.on('timeout', () => {
      if (!resolved) {
        resolved = true;
        socket.destroy();
        resolve(false);
      }
    });
    socket.on('error', () => {
      if (!resolved) {
        resolved = true;
        socket.destroy();
        resolve(false);
      }
    });
    socket.connect(port, host);
  });
}

async function waitForPort(port, host = '127.0.0.1', maxWaitMs = 12000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    if (await isPortOpen(port, host, 400)) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function autoBackendPlugin(targetUrl) {
  let backendProcess = null;
  const isLocal = !targetUrl || targetUrl.includes('127.0.0.1') || targetUrl.includes('localhost');

  return {
    name: 'auto-backend-plugin',
    async configureServer() {
      if (!isLocal) {
        console.log(`\x1b[36m[Vite Proxy] Using remote deployed backend: ${targetUrl}\x1b[0m`);
        return;
      }

      const portOpen = await isPortOpen(5000);
      if (portOpen) {
        console.log('\x1b[32m[Vite] Backend is already running on port 5000.\x1b[0m');
        return;
      }

      console.log('\x1b[33m[Vite] Backend not detected on port 5000. Auto-starting backend server...\x1b[0m');
      const backendDir = path.resolve(__dirname, '../backend');
      const serverScript = path.resolve(backendDir, 'src/server.js');

      backendProcess = spawn(process.execPath, [serverScript], {
        cwd: backendDir,
        stdio: 'inherit',
        env: { ...process.env, PORT: '5000' },
      });

      backendProcess.on('error', (err) => {
        console.error('\x1b[31m[Vite] Failed to spawn backend process:\x1b[0m', err.message);
      });

      const ready = await waitForPort(5000);
      if (ready) {
        console.log('\x1b[32m[Vite] Backend successfully running on http://127.0.0.1:5000\x1b[0m');
      } else {
        console.warn('\x1b[33m[Vite] Backend started, waiting for connection...\x1b[0m');
      }

      const cleanup = () => {
        if (backendProcess) {
          try {
            backendProcess.kill();
          } catch {}
          backendProcess = null;
        }
      };

      process.once('exit', cleanup);
      process.once('SIGINT', cleanup);
      process.once('SIGTERM', cleanup);
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_API_URL || env.VITE_API_PROXY_TARGET || process.env.VITE_API_URL || process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5000';

  return {
    plugins: [
      react(),
      autoBackendPlugin(target),
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target,
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
  };
});
