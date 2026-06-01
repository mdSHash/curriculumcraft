import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `base` is relative when the build is destined for GitHub Pages
// (served at /<repo>/), but root-absolute for local dev / Docker.
//
// Set APP_BUILD_TARGET=pages in CI to build for Pages. Honor the legacy
// MATHCRAFT_BUILD_TARGET name too so existing CI configs keep working
// during the rename.
//
// Pages base path is configurable via VITE_PAGES_BASE (defaults to
// /curriculumcraft/). Hard cutover from /mathcraft/ — older bookmarks
// will 404, by design (per Phase 3 cutover decision).
const buildTarget =
  process.env.APP_BUILD_TARGET || process.env.MATHCRAFT_BUILD_TARGET || 'app'
const pagesBase = process.env.VITE_PAGES_BASE || '/curriculumcraft/'

export default defineConfig({
  base: buildTarget === 'pages' ? pagesBase : '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
