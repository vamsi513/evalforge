import { test, expect } from "./fixtures";

/**
 * UI tests against the main frontend + backend pair (ports 3101 / 8101).
 *
 * These run in declaration order with workers: 1. None of them reads state
 * another one wrote: the eval in "runs an evaluation" only adds rows, and
 * nothing here asserts a row count. The empty-state assertion lives in its own
 * project with its own database for exactly that reason.
 */
test.describe("dashboard", () => {
  test("loads with its heading, navigation and metric cards", async ({ dashboard, nav, data }) => {
    await dashboard.goto();

    await expect(dashboard.heading).toBeVisible();
    await expect(dashboard.healthOk).toBeVisible();

    // Five sidebar links, one per page.
    await expect(nav.sidebarLinks).toHaveCount(data.pages.length);
    for (const { navLabel } of data.pages) {
      await expect(nav.sidebarLink(navLabel)).toBeVisible();
    }

    // All five metric cards render their label.
    for (const label of data.metricLabels) {
      await expect(dashboard.metricCard(label)).toBeVisible();
    }
  });

  test("runs an evaluation and renders the scored results", async ({ dashboard }) => {
    await dashboard.goto();

    // Idle before the run: no result panel, and the prompt to pick a scenario.
    await expect(dashboard.idleHint).toBeVisible();
    await expect(dashboard.resultPanel).toHaveCount(0);

    await dashboard.runEval();

    // An average score, and one row per scored sample. The demo scenarios each
    // carry three samples, scored by the deterministic heuristic evaluators.
    await expect(dashboard.averageScore).toBeVisible();
    await expect(dashboard.resultPanel.getByText("3 cases scored", { exact: false })).toBeVisible();
    await expect(dashboard.caseRows()).toHaveCount(3);
    await expect(dashboard.demoError).toHaveCount(0);
  });

  test("switches scenario and the run button follows", async ({ dashboard, data }) => {
    await dashboard.goto();

    const [first, second, third] = data.demoScenarios;

    // "general" is selected on load.
    await expect(dashboard.scenarioTab(first.label)).toHaveAttribute("aria-selected", "true");
    await expect(dashboard.runButton).toHaveText(new RegExp(`Run ${first.label}`));

    for (const scenario of [second, third]) {
      await dashboard.scenarioTab(scenario.label).click();
      await expect(dashboard.scenarioTab(scenario.label)).toHaveAttribute("aria-selected", "true");
      await expect(dashboard.runButton).toHaveText(new RegExp(`Run ${scenario.label.replace("&", "&")}`));
    }

    // Only one tab is selected at a time.
    await expect(dashboard.scenarioTablist.getByRole("tab", { selected: true })).toHaveCount(1);
  });
});

test.describe("navigation", () => {
  test("reaches every page from the sidebar", async ({ page, nav, data }) => {
    await page.goto("/");

    for (const { navLabel, heading, path } of data.pages) {
      await nav.sidebarLink(navLabel).click();
      await expect(page).toHaveURL(new RegExp(`${path.replace("/", "\\/")}$`));
      await nav.expectHeading(heading);
    }
  });
});

test.describe("responsive", () => {
  test("swaps the sidebar for a mobile drawer at 375px", async ({ page, nav, data }) => {
    await page.setViewportSize(data.mobileViewport);
    await page.goto("/");

    // Steps, so a failure names the phase it happened in rather than just
    // reporting that the test timed out.
    await test.step("sidebar gives way to the mobile header", async () => {
      await expect(nav.sidebar).toBeHidden();
      await expect(nav.mobileHeader).toBeVisible();
      await nav.expectDrawerClosed();
    });

    await test.step("hamburger opens the drawer", async () => {
      await nav.openMenuButton.click();
      await nav.expectDrawerOpen();
    });

    await test.step("the drawer's own close button closes it", async () => {
      // Not the hamburger: the backdrop covers it while the drawer is open.
      await nav.drawerCloseButton.click();
      await nav.expectDrawerClosed();
    });

    await test.step("a drawer link navigates and the drawer closes", async () => {
      await nav.openMenuButton.click();
      await nav.expectDrawerOpen();
      // Only clicked while open: the drawer stays in the DOM when closed, so
      // clicking it closed would wait on an off-screen element.
      await nav.drawerLink("Datasets").click();
      await expect(page).toHaveURL(/\/datasets$/);
      await nav.expectHeading("Datasets");
      await nav.expectDrawerClosed();
    });
  });
});
