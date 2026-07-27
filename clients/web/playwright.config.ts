import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:15173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "MOBILITY_API_PORT=18000 bash scripts/run_api.sh",
      cwd: "../..",
      url: "http://127.0.0.1:18000/health",
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command:
        "VITE_DEV_PORT=15173 VITE_PROXY_TARGET=http://127.0.0.1:18000 npm run dev",
      cwd: ".",
      url: "http://127.0.0.1:15173",
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
})
