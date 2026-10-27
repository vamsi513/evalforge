import { Page, Locator, expect } from "@playwright/test";

/**
 * The two navigation surfaces. Which one is visible is decided by a CSS media
 * query at max-width: 700px -- the sidebar is hidden and a hamburger header
 * takes over -- so both live here rather than in a page-specific object.
 */
export class NavPage {
  readonly sidebar: Locator;
  readonly sidebarLinks: Locator;
  readonly mobileHeader: Locator;
  readonly openMenuButton: Locator;
  readonly mobileDrawer: Locator;
  readonly mobileBackdrop: Locator;
  readonly drawerCloseButton: Locator;

  constructor(private readonly page: Page) {
    this.sidebar = page.getByRole("navigation", { name: "Primary navigation" });
    this.sidebarLinks = this.sidebar.getByRole("link");
    this.mobileHeader = page.locator(".mobile-header");
    this.openMenuButton = page.getByRole("button", { name: "Open menu" });
    this.mobileDrawer = page.getByRole("navigation", { name: "Mobile navigation" });
    // The drawer is hidden with transform: translateX(-100%), not display:none,
    // so it stays "visible" to Playwright even when closed and its links stay in
    // the accessibility tree. The backdrop is the only element that is actually
    // mounted conditionally, and the hamburger carries aria-expanded, so those
    // two are what open/closed is asserted on -- never the drawer's visibility.
    this.mobileBackdrop = page.locator(".mobile-backdrop");
    // Closing happens from inside the drawer, not from the hamburger. The
    // backdrop is position:fixed inset:0 at z-index 101 and the mobile header
    // sits at z-index 100, so while the drawer is open the backdrop covers the
    // hamburger completely and a click on it never lands. The drawer's own
    // close button is at z-index 102, above the backdrop, so it is the control
    // a user can actually reach.
    this.drawerCloseButton = this.mobileDrawer.getByRole("button", {
      name: "Close navigation menu",
    });
  }

  sidebarLink(name: string): Locator {
    return this.sidebar.getByRole("link", { name, exact: true });
  }

  drawerLink(name: string): Locator {
    return this.mobileDrawer.getByRole("link", { name, exact: true });
  }

  /** The hamburger, whichever label it currently carries. */
  menuButton(): Locator {
    return this.mobileHeader.getByRole("button", { name: /menu$/ });
  }

  async expectDrawerOpen() {
    await expect(this.menuButton()).toHaveAttribute("aria-expanded", "true");
    await expect(this.mobileBackdrop).toBeVisible();
  }

  async expectDrawerClosed() {
    await expect(this.menuButton()).toHaveAttribute("aria-expanded", "false");
    await expect(this.mobileBackdrop).toHaveCount(0);
  }

  async expectHeading(name: string) {
    await expect(this.page.getByRole("heading", { level: 1, name })).toBeVisible();
  }
}
