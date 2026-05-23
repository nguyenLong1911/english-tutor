import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

const outputDir = path.resolve(process.cwd(), '..', '..', 'output', 'demo-video')

export default defineConfig({
  testDir: '.',
  timeout: process.env.DEMO_USE_REAL_API === '1' ? 180_000 : 90_000,
  outputDir,
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.DEMO_BASE_URL || 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: 'vi-VN',
    timezoneId: 'Asia/Ho_Chi_Minh',
    colorScheme: 'light',
    video: {
      mode: 'on',
      size: { width: 1440, height: 900 },
    },
    trace: 'retain-on-failure',
  },
  webServer: process.env.DEMO_BASE_URL
    ? undefined
    : {
        command: 'npm run dev -- --host 127.0.0.1',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: true,
        timeout: 120_000,
      },
})
