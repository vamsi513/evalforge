import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Repo root. The backend is a Python app one level up from this package.
const REPO_ROOT = path.resolve(__dirname, "..");

// The suite's SQLite files live in a temp directory, not the repo.
//
// Two reasons. Processes Playwright spawns could not write inside the repo
// working tree on this machine -- SQLite reported "attempt to write a readonly
// database" on the first INSERT while reads kept working, and the same uvicorn
// command started by hand wrote fine -- so the databases had to move somewhere
// unambiguously writable. It is also simply cleaner: a test run leaves nothing
// behind in the project. global-setup deletes them before every run.
export const E2E_DB_DIR = path.join(os.tmpdir(), "evalforge-e2e");

// Created AND emptied here, in the config module, rather than in globalSetup.
// Playwright starts the webServer processes before globalSetup runs, so doing
// either there is wrong in a different way: creating the directory there is too
// late (uvicorn dies with "unable to open database file"), and deleting the
// files there is worse -- it unlinks the SQLite files the running backends
// already hold open, after which reads keep being served from the open handle
// while every write fails with "attempt to write a readonly database". That
// failure is silent and looks exactly like a permissions problem.
//
// Doing both at config load means the directory is clean before any server
// starts and nothing is removed from under a live process.
// The delete is guarded to the main process. Playwright re-imports this config
// inside every worker, and an unguarded top-level rmSync therefore fired again
// mid-run and unlinked the databases a second time -- the same
// deleted-while-open failure, just triggered later. TEST_WORKER_INDEX is set
// only in workers.
if (process.env.TEST_WORKER_INDEX === undefined) {
  fs.rmSync(E2E_DB_DIR, { recursive: true, force: true });
}
fs.mkdirSync(E2E_DB_DIR, { recursive: true });

// Python interpreter that has the backend installed. Overridable so CI and a
// local machine can differ without editing this file.
const PYTHON = process.env.E2E_PYTHON ?? "python3.11";

// Four servers, because three of the eleven tests need a different backend
// state than the rest and sharing one would make them depend on each other:
//
//   8101 / 3101  the main pair. UI and API tests run against this.
//   8102 / 3102  a second pair with its own SQLite file, so the empty-state
//                test sees a database no other test has written to.
//   3103         frontend only, pointed at a port nothing listens on, so the
//                error-state test exercises the app's real API-unreachable
//                path rather than a mocked one.
const BACKEND_PORT = 8101;
const BACKEND_EMPTY_PORT = 8102;
const FRONTEND_PORT = 3101;
const FRONTEND_EMPTY_PORT = 3102;
const FRONTEND_BROKEN_PORT = 3103;
const DEAD_PORT = 9099;

// JUDGE_PROVIDER=mock and DEFAULT_USER_ROLE=admin live here and in the CI
// workflow only. They are never application defaults: the app ships
// judge_provider="mock" already but default_user_role="viewer", and write
// endpoints return 403 under viewer. Granting the role here keeps the suite
// keyless without loosening anything the app does in production.
function backendEnv(dbFile: string, port: number) {
  return {
    // Spread the real environment. Playwright replaces the child environment
    // with whatever `env` contains rather than merging, so without this the
    // backend starts with no HOME, TMPDIR or PATH -- and SQLite, unable to
    // create its journal and temp files, reports "attempt to write a readonly
    // database" on the first INSERT while reads keep working.
    ...process.env,
    APP_ENV: "dev",
    JUDGE_PROVIDER: "mock",
    DEFAULT_USER_ROLE: "admin",
    DATABASE_URL: `sqlite:///${path.join(E2E_DB_DIR, dbFile)}`,
    // One MLflow file per backend. Both instances sharing a single SQLite file
    // meant two uvicorn processes initialising the same schema at once.
    MLFLOW_TRACKING_URI: `sqlite:///${path.join(E2E_DB_DIR, `${dbFile}-mlflow.db`)}`,
    AUTO_CREATE_TABLES: "true",
    PORT: String(port),
  };
}

function backendServer(dbFile: string, port: number) {
  return {
    command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
    cwd: REPO_ROOT,
    url: `http://127.0.0.1:${port}/health`,
    env: backendEnv(dbFile, port),
    // Never reuse. A leftover server from another session may have been started
    // with frontend/.env.local in effect, which carries a real API key and the
    // live EC2 URL -- reusing it would silently point the suite at production.
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe" as const,
    stderr: "pipe" as const,
  };
}

function frontendServer(port: number, apiUrl: string) {
  return {
    // `next start`, not `next dev`. Turbopack's dev server refuses to run a
    // second instance from the same directory ("Another next dev server is
    // already running"), and this suite needs three frontends on three ports.
    // `next start` has no such lock, so the build runs once via the
    // pretest:e2e script and all three serve from it.
    command: `npx next start --port ${port}`,
    cwd: __dirname,
    url: `http://127.0.0.1:${port}/`,
    env: {
      ...process.env,
      EVALFORGE_API_URL: apiUrl,
      // Blanked deliberately. Next loads frontend/.env.local automatically,
      // and on a developer machine that file holds a real EVALFORGE_API_KEY --
      // without this line the suite would quietly send someone's live key and
      // would not actually be proving it runs keyless. lib/api.ts and the proxy
      // routes both treat an empty value as "send no X-API-Key header", which
      // the dev-mode backend accepts.
      EVALFORGE_API_KEY: "",
    },
    reuseExistingServer: false,
    timeout: 180_000,
    stdout: "pipe" as const,
    stderr: "pipe" as const,
  };
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { outputFolder: "playwright-report", open: "never" }], ["list"]],

  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "api",
      testMatch: /api\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: process.env.E2E_API_URL ?? `http://127.0.0.1:${BACKEND_PORT}`,
      },
    },
    {
      name: "ui",
      testMatch: /ui\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: process.env.E2E_BASE_URL ?? `http://127.0.0.1:${FRONTEND_PORT}`,
      },
    },
    {
      // Own backend + own SQLite file, so this never races the eval that
      // ui.spec.ts runs.
      name: "empty-state",
      testMatch: /empty-state\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://127.0.0.1:${FRONTEND_EMPTY_PORT}`,
      },
    },
    {
      // Frontend only, pointed at a dead port.
      name: "error-state",
      testMatch: /error-state\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://127.0.0.1:${FRONTEND_BROKEN_PORT}`,
      },
    },
  ],

  webServer: [
    backendServer("e2e.db", BACKEND_PORT),
    backendServer("e2e-empty.db", BACKEND_EMPTY_PORT),
    frontendServer(FRONTEND_PORT, `http://127.0.0.1:${BACKEND_PORT}`),
    frontendServer(FRONTEND_EMPTY_PORT, `http://127.0.0.1:${BACKEND_EMPTY_PORT}`),
    frontendServer(FRONTEND_BROKEN_PORT, `http://127.0.0.1:${DEAD_PORT}`),
  ],
});
