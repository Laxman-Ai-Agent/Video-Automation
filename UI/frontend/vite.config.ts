import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import http from 'node:http'
import https from 'node:https'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'
  const isHttps = backendTarget.startsWith('https')

  const agent = isHttps
    ? new https.Agent({ keepAlive: true, maxSockets: 50, keepAliveMsecs: 15000 })
    : new http.Agent({ keepAlive: true, maxSockets: 50, keepAliveMsecs: 15000 })

  const proxyConfig = {
    target: backendTarget,
    changeOrigin: true,
    secure: false,
    agent: agent,
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      host: '127.0.0.1',
      watch: {
        ignored: ['**/node_modules/**', '**/.venv/**', '**/.git/**', '**/projects/**', '**/dist/**', '**/reports/**']
      },
      hmr: {
        overlay: true
      },
      proxy: {
        '/api': {
          ...proxyConfig,
          rewrite: (path: string) => path.replace(/^\/api/, '')
        },
        '/projects': proxyConfig,
        '/agents': proxyConfig,
        '/skills': proxyConfig,
        '/health': proxyConfig,
        '/stream': {
          target: backendTarget,
          changeOrigin: true,
          secure: false
        },
        '/llm': proxyConfig,
        '/rules': proxyConfig,
        '/work-log': proxyConfig,
        '/approvals': proxyConfig
      }
    }
  }
})
