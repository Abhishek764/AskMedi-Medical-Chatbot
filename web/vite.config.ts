import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The dev server proxies /v1 to the FastAPI backend, so the browser sees one origin and the
// httpOnly refresh cookie (path /v1/auth) works without CORS. In production, route /v1 to the
// API on the same domain (Cloudflare or the hosting provider's rewrites).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/v1': { target: process.env.ASKMEDI_API ?? 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
