import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import http from 'node:http'

const keepAliveAgent = new http.Agent({
  keepAlive: true,
  maxSockets: 50,
  keepAliveMsecs: 15000
})

export default defineConfig({
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
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/projects': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent
      },
      '/agents': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent
      },
      '/skills': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent
      },
      '/stream': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/llm': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent
      },
      '/rules': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        agent: keepAliveAgent
      }
    }
  }
})
