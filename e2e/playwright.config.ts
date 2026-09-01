import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://host.docker.internal:5173',
    trace: 'retain-on-failure',
  },
})
