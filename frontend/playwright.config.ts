import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PLAYWRIGHT_PORT ?? 3100);

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: Number(process.env.PLAYWRIGHT_WORKERS ?? 1),
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 1,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `npm run dev -- --hostname 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      API_INTERNAL_URL: process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000",
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
      AUTH_PASSWORD_ENABLED: process.env.AUTH_PASSWORD_ENABLED ?? "true",
      NEXT_PUBLIC_SUPPORT_URL:
        process.env.NEXT_PUBLIC_SUPPORT_URL ?? "https://support.sentinelpay.test",
      NEXT_PUBLIC_PRIVACY_CONTACT_URL:
        process.env.NEXT_PUBLIC_PRIVACY_CONTACT_URL ?? "https://privacy.sentinelpay.test/contato",
      NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL:
        process.env.NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL ?? "privacidade@sentinelpay.test",
      NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL ?? `http://127.0.0.1:${port}`,
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
