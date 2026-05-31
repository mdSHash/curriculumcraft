import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `base` is relative when the build is destined for GitHub Pages
// (served at /<repo>/), but root-absolute for local dev / Docker.
// Set MATHCRAFT_BUILD_TARGET=pages in CI to build for Pages.
const buildTarget = process.env.MATHCRAFT_BUILD_TARGET || 'app'

export default defineConfig({
  base: buildTarget === 'pages' ? '/mathcraft/' : '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
