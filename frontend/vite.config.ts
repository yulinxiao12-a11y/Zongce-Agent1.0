import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(() => {
  const backendUrl = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:5001'

  return {
    plugins: [vue()],
    server: {
      host: '127.0.0.1',
      port: 5174,
      strictPort: true,
      proxy: {
        '/admin': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/api': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/static': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/uploads': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/view-as-student': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/back-to-admin': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/logout': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})
