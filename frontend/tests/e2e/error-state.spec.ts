import { test, expect } from "./fixtures";

/**
 * API-unreachable state, in its own Playwright project.
 *
 * This project's frontend (port 3103) is started with EVALFORGE_API_URL
 * pointing at a port nothing listens on. Every page wraps its API calls in
 * .catch() with zero-value fallbacks, so the real behaviour under an
 * unreachable backend is a rendered page with a warning badge and zeroed
 * metrics -- not a crash and not a mock.
 */
test("dashboard degrades to a warning and zeroed metrics when the API is unreachable", async ({
  dashboard,
  nav,
  data,
}) => {
  await dashboard.goto();

  // The page renders rather than erroring.
  await expect(dashboard.heading).toBeVisible();
  await expect(nav.sidebarLinks).toHaveCount(data.pages.length);

  // Health reports the failure.
  await expect(dashboard.healthUnreachable).toBeVisible();
  await expect(dashboard.healthOk).toHaveCount(0);

  // Metric cards still render, carrying their zero fallbacks.
  for (const label of data.metricLabels) {
    await expect(dashboard.metricCard(label)).toBeVisible();
  }

  // The demo widget is present and has produced no result.
  await expect(dashboard.runButton).toBeVisible();
  await expect(dashboard.resultPanel).toHaveCount(0);
});
