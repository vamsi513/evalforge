import { Page, Locator, expect } from "@playwright/test";

/**
 * The "/runs" page.
 *
 * It has two mutually exclusive branches: an empty-state block when the
 * backend returns no runs, and a results table otherwise. Both are addressed
 * by role or visible text, so no data-testid was needed.
 */
export class RunsPage {
  readonly heading: Locator;
  readonly emptyState: Locator;
  readonly emptyStateHint: Locator;
  readonly table: Locator;
  readonly rows: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { level: 1, name: "Eval Runs" });
    this.emptyState = page.getByText("No eval runs yet", { exact: true });
    this.emptyStateHint = page.getByText(/Seed 3 demo experiments/);
    this.table = page.getByRole("table");
    this.rows = this.table.locator("tbody tr");
  }

  async goto() {
    await this.page.goto("/runs");
  }

  async expectEmpty() {
    await expect(this.emptyState).toBeVisible();
    await expect(this.table).toHaveCount(0);
  }
}
