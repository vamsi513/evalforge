import { test, expect } from "./fixtures";

/**
 * Empty state, in its own Playwright project.
 *
 * It runs against the second backend/frontend pair (8102 / 3102), whose SQLite
 * file is created fresh by global-setup and written to by nothing else. Sharing
 * the main database would make this test's result depend on whether the eval in
 * ui.spec.ts had already run, which is the kind of coupling that makes a suite
 * untrustworthy.
 */
test("runs page shows its empty state against a fresh database", async ({ runs, nav }) => {
  await runs.goto();

  await expect(runs.heading).toBeVisible();

  // The page's own empty branch, not a blank screen: a message and the hint
  // offering to seed demo data.
  await expect(runs.emptyState).toBeVisible();
  await expect(runs.emptyStateHint).toBeVisible();

  // And no results table at all, rather than a table with zero rows.
  await expect(runs.table).toHaveCount(0);

  // The rest of the page still works -- an empty backend is not an error.
  await expect(nav.sidebarLinks).toHaveCount(5);
});
