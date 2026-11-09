import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/monitor': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/status': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/analyze': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/download-report': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
