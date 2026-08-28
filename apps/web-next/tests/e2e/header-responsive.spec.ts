import { expect, test, type Page } from "@playwright/test";

const desktopWidths = [1024, 1180, 1181, 1225, 1280, 1366, 1440] as const;
const mobileWidths = [360, 390, 768, 980] as const;

async function mockAuthenticatedAdmin(page: Page) {
  await page.route("**/api/**", route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me" || pathname === "/api/auth/me/") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          username: "owner",
          email: "owner@example.com",
          role: "admin",
          is_active: true,
        }),
      });
    }

    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Header layout fixture" }),
    });
  });
}

type HeaderAudit = {
  documentOverflow: number;
  headerOverflow: number;
  headerHeight: number;
  regions: Record<string, {
    left: number;
    top: number;
    right: number;
    bottom: number;
    centerY: number;
  }>;
  overlaps: string[];
  clippedControls: string[];
  rowCount: number;
};

async function auditVisibleHeader(page: Page): Promise<HeaderAudit> {
  return page.locator(".site-header").evaluate(header => {
    const tolerance = 1;
    const rowTolerance = 10;
    const visible = (element: Element) => {
      const style = window.getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    };
    const boxFor = (element: Element) => {
      const box = element.getBoundingClientRect();
      return {
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom,
        centerY: box.top + box.height / 2,
      };
    };

    const selectors = {
      brand: ".site-header__brand",
      search: ".global-search",
      navigation: ".site-header__nav",
      actions: ".site-header__action",
      menu: ".mobile-menu",
    } as const;
    const entries = Object.entries(selectors)
      .map(([name, selector]) => [name, header.querySelector(selector)] as const)
      .filter((entry): entry is readonly [string, Element] => Boolean(entry[1]) && visible(entry[1]!));
    const regions = Object.fromEntries(entries.map(([name, element]) => [name, boxFor(element)]));

    const overlaps: string[] = [];
    for (let leftIndex = 0; leftIndex < entries.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < entries.length; rightIndex += 1) {
        const [leftName, leftElement] = entries[leftIndex];
        const [rightName, rightElement] = entries[rightIndex];
        const left = boxFor(leftElement);
        const right = boxFor(rightElement);
        const overlapWidth = Math.min(left.right, right.right) - Math.max(left.left, right.left);
        const overlapHeight = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
        if (overlapWidth > tolerance && overlapHeight > tolerance) {
          overlaps.push(`${leftName} <> ${rightName}`);
        }
      }
    }

    const clippedControls = Array.from(header.querySelectorAll<HTMLElement>("a, button, input"))
      .filter(visible)
      .map(element => ({ element, box: boxFor(element) }))
      .filter(({ box }) => box.left < -tolerance || box.right > window.innerWidth + tolerance)
      .map(({ element }) => (element.getAttribute("aria-label") || element.textContent || element.className).trim());

    const rowCenters: number[] = [];
    for (const [, element] of entries) {
      const centerY = boxFor(element).centerY;
      if (!rowCenters.some(existing => Math.abs(existing - centerY) <= rowTolerance)) {
        rowCenters.push(centerY);
      }
    }

    const headerBox = header.getBoundingClientRect();
    return {
      documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
      headerOverflow: header.scrollWidth - header.clientWidth,
      headerHeight: headerBox.height,
      regions,
      overlaps,
      clippedControls,
      rowCount: rowCenters.length,
    };
  });
}

async function expectDesktopControls(page: Page) {
  const header = page.locator(".site-header");
  const search = header.getByRole("search");
  const navigation = header.getByRole("navigation", { name: "Primary navigation" });
  const actions = header.locator(".site-header__action");

  await expect(search).toBeVisible();
  await expect(search.getByRole("textbox", { name: "Search marketplace" })).toBeVisible();
  await expect(search.getByRole("button", { name: "Search products" })).toBeVisible();
  await expect(navigation).toBeVisible();
  for (const label of ["Dashboard", "Orders", "Catalog", "Research"]) {
    await expect(navigation.getByRole("link", { name: label, exact: true })).toBeVisible();
  }
  await expect(actions).toBeVisible();
  await expect(actions.locator(".locale-toggle")).toBeVisible();
  await expect(actions.locator(".account-chip")).toBeVisible();
  await expect(actions.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(header.getByRole("button", { name: "Open navigation" })).toBeHidden();
}

test("@public authenticated header uses intentional responsive rows without overlap", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "mobile-chromium", "Desktop breakpoint sweep runs in the desktop project");
  test.setTimeout(60_000);
  await mockAuthenticatedAdmin(page);

  for (const width of desktopWidths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator(".site-header--authenticated")).toBeVisible();
    await expectDesktopControls(page);

    const audit = await auditVisibleHeader(page);
    const expectedRows = width <= 1180 ? 2 : 1;
    expect.soft(audit.documentOverflow, `${width}px document overflow`).toBeLessThanOrEqual(1);
    expect.soft(audit.headerOverflow, `${width}px header overflow`).toBeLessThanOrEqual(1);
    expect.soft(audit.overlaps, `${width}px header region overlap`).toEqual([]);
    expect.soft(audit.clippedControls, `${width}px clipped controls`).toEqual([]);
    expect.soft(audit.rowCount, `${width}px intentional header row count`).toBe(expectedRows);
    expect.soft(audit.headerHeight, `${width}px compact header height`).toBeLessThanOrEqual(expectedRows === 1 ? 82 : 132);

    const nav = audit.regions.navigation;
    const search = audit.regions.search;
    const actions = audit.regions.actions;
    expect.soft(nav, `${width}px navigation region`).toBeTruthy();
    expect.soft(search, `${width}px search region`).toBeTruthy();
    expect.soft(actions, `${width}px actions region`).toBeTruthy();
    if (expectedRows === 1 && nav && search && actions) {
      expect.soft(Math.abs(nav.centerY - search.centerY), `${width}px nav/search alignment`).toBeLessThanOrEqual(10);
      expect.soft(Math.abs(actions.centerY - search.centerY), `${width}px actions/search alignment`).toBeLessThanOrEqual(10);
    } else if (nav && search && actions) {
      expect.soft(nav.top, `${width}px second-row navigation`).toBeGreaterThanOrEqual(Math.max(search.bottom, actions.bottom) - 1);
    }
  }
});

test("@public compact header keeps search and accessible navigation on mobile", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Mobile breakpoint sweep runs in the mobile project");
  test.setTimeout(60_000);
  await mockAuthenticatedAdmin(page);

  for (const width of mobileWidths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const header = page.locator(".site-header--authenticated");
    await expect(header).toBeVisible();
    await expect(header.getByRole("search")).toBeVisible();
    await expect(header.getByRole("textbox", { name: "Search marketplace" })).toBeVisible();
    await expect(header.getByRole("button", { name: "Search products" })).toBeVisible();
    await expect(header.locator(".site-header__action")).toBeHidden();

    const menu = header.locator(".mobile-menu");
    const navigation = header.getByRole("navigation", { name: "Primary navigation" });
    await expect(menu).toBeVisible();
    await expect(menu).toHaveAccessibleName("Open navigation");
    await expect(menu).toHaveAttribute("aria-controls", "primary-navigation");
    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await expect(navigation).toBeHidden();

    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
    await expect(menu).toHaveAccessibleName("Close navigation");
    await expect(navigation).toBeVisible();
    for (const label of ["Dashboard", "Orders", "Catalog", "Research"]) {
      await expect(navigation.getByRole("link", { name: label, exact: true })).toBeVisible();
    }
    await expect(navigation.getByRole("link", { name: /Account/ })).toBeVisible();
    await expect(navigation.getByRole("button", { name: "Sign out" })).toBeVisible();
    await expect(navigation.getByRole("button", { name: "Switch to Bangla" })).toBeVisible();

    await page.keyboard.press("Tab");
    await expect.poll(() => navigation.evaluate(node => node.contains(document.activeElement)), {
      message: `${width}px opened navigation receives keyboard focus`,
    }).toBe(true);

    const audit = await auditVisibleHeader(page);
    expect.soft(audit.documentOverflow, `${width}px mobile document overflow`).toBeLessThanOrEqual(1);
    expect.soft(audit.headerOverflow, `${width}px mobile header overflow`).toBeLessThanOrEqual(1);
    expect.soft(audit.overlaps, `${width}px mobile header region overlap`).toEqual([]);
    expect.soft(audit.clippedControls, `${width}px mobile clipped controls`).toEqual([]);
    expect.soft(audit.rowCount, `${width}px brand/search/navigation rows`).toBe(3);
  }
});
