import { defineConfig, devices } from '@playwright/test'

const apiPort = 8193
const webPort = 4193

export default defineConfig({
  testDir: 'e2e',
  timeout: 45_000,
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    ...devices['Desktop Chrome'],
    launchOptions: {
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `uv run --locked --project ../backend uvicorn trl.api.app:app --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/healthz`,
      env: { TRL_DB: `../.local/e2e/run-${process.pid}.sqlite` },
    },
    {
      command: `corepack pnpm exec vite --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: `http://127.0.0.1:${webPort}`,
      env: { TRL_API: `http://127.0.0.1:${apiPort}` },
    },
  ],
})
