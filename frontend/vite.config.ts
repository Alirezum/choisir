import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Build straight into the Python package so `choosier --web` serves it,
// and proxy the API during `npm run dev`.
export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../choosier/web_static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8765',
    },
  },
})
