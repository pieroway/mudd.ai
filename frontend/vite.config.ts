import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    restoreMocks: true,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false,
    allowedHosts: ['host.docker.internal'],
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
