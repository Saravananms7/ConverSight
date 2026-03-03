import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/transcribe': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/analyze': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/policy': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/detect-topics': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
