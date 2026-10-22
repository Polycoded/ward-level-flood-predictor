/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import vercel from './vercel.json'

// `vite preview` serves the production security headers from vercel.json, so CSP problems show up locally.
const productionHeaders = Object.fromEntries(
  vercel.headers.find((h) => h.source === '/(.*)')!.headers.map((h) => [h.key, h.value])
)

const apiProxy = {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: {
    port: 4173,
    headers: productionHeaders,
    proxy: apiProxy,
  },
  build: {
    outDir: 'dist',
    // source maps are uploaded to Sentry separately when configured; keep them out of the public bundle
    sourcemap: false,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
    restoreMocks: true,
    // components talk to the bundled mock API unless a test injects its own client
    env: { VITE_USE_MOCK: 'true' },
  },
})
