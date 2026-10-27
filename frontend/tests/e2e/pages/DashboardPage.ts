import { Page, Locator, expect } from "@playwright/test";

/**
 * The "/" dashboard, including the live-eval widget.
 *
 * Everything is addressed by role or visible text. The widget already exposes a
 * proper tablist with aria-selected, the run button's accessible name is
 * "Run <scenario>", and the result panel is role="tabpanel" -- so no
 * data-testid attributes were added to the app for any of this.
 */
export class DashboardPage {
  readonly heading: Locator;
  readonly healthOk: Locator;
  readonly healthUnreachable: Locator;
  readonly runButton: Locator;
  readonly scenarioTablist: Locator;
  readonly resultPanel: Locator;
  readonly averageScore: Locator;
  readonly idleHint: Locator;
  readonly demoError: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { level: 1, name: "Overview" });
    // Exact strings the dashboard renders for health; verified against app/page.tsx.
    this.healthOk = page.getByText("All systems operational", { exact: true });
    this.healthUnreachable = page.getByText("API unreachable", { exact: true });
    // Matches "Run General Knowledge" / "Run Customer Support" / "Run Code & Tech".
    this.runButton = page.getByRole("button", { name: /^Run / });
    this.scenarioTablist = page.getByRole("tablist", { name: "Evaluation scenario" });
    this.resultPanel = page.getByRole("tabpanel");
    this.averageScore = this.resultPanel.getByText(/\d+% avg/);
    this.idleHint = page.getByText(/Pick a scenario and click/);
    this.demoError = page.getByText(/Demo run failed|^Error:/);
  }

  async goto() {
    await this.page.goto("/");
  }

  scenarioTab(label: string): Locator {
    return this.scenarioTablist.getByRole("tab").filter({ hasText: label });
  }

  metricCard(label: string): Locator {
    return this.page.getByText(label, { exact: true });
  }

  /**
   * Clicks Run and waits for the eval to come back.
   *
   * The wait is on the /api/demo response and then on the result panel
   * appearing -- never on a timer. The heuristic evaluators run in-process with
   * no LLM call, but the request still crosses two servers.
   */
  async runEval() {
    const response = this.page.waitForResponse(
      (r) => r.url().includes("/api/demo") && r.request().method() === "POST",
    );
    await this.runButton.click();
    await response;
    await expect(this.resultPanel).toBeVisible();
  }

  /** The per-case rows inside the result panel, one per scored sample. */
  caseRows(): Locator {
    return this.resultPanel.getByText(/\d+%$/);
  }
}
