import { test as base, expect } from "@playwright/test";
import scenarios from "./data/scenarios.json";
import { DashboardPage } from "./pages/DashboardPage";
import { RunsPage } from "./pages/RunsPage";
import { NavPage } from "./pages/NavPage";

// Shared fixture. Page objects are constructed per test so a spec never has to
// build one itself, and the JSON test data arrives the same way so no spec
// hardcodes a label, path or payload.
type Fixtures = {
  dashboard: DashboardPage;
  runs: RunsPage;
  nav: NavPage;
  data: typeof scenarios;
};

export const test = base.extend<Fixtures>({
  dashboard: async ({ page }, use) => {
    await use(new DashboardPage(page));
  },
  runs: async ({ page }, use) => {
    await use(new RunsPage(page));
  },
  nav: async ({ page }, use) => {
    await use(new NavPage(page));
  },
  data: async ({}, use) => {
    await use(scenarios);
  },
});

export { expect, scenarios };
