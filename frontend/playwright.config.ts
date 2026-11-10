import { defineConfig } from "@playwright/test";

// Starts the real FastAPI backend (fresh SQLite db, mock LLM + placeholder art) and the production Next.js server.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:3000", viewport: { width: 1440, height: 900 }, trace: "off" },
  webServer: [
    {
      command: "sh -c 'rm -rf data/e2e && mkdir -p data/e2e && DATABASE_URL=sqlite:///./data/e2e/rpg.db ASSET_DIR=./data/e2e/assets python3 -m uvicorn app.main:create_app --factory --port 8000'",
      cwd: "../backend", url: "http://127.0.0.1:8000/api/health", reuseExistingServer: false, timeout: 60_000,
    },
    { command: "npm run start", url: "http://127.0.0.1:3000", reuseExistingServer: false, timeout: 60_000 },
  ],
});
