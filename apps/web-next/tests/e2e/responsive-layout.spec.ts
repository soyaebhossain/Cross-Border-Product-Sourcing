import { expect, test } from "@playwright/test";

const routes = [
  "/",
  "/products",
  "/products/xiaomi-smart-air-purifier-4-compact",
  "/categories",
  "/quote",
  "/research",
  "/login",
  "/signup",
];

const accountRoutes = [
  "/account",
  "/account/invoices",
  "/account/notifications",
  "/account/orders",
  "/account/profile",
  "/account/saved-quotes",
  "/account/support",
];

const adminRoutes = [
  "/admin",
  "/admin/ai-reviews",
  "/admin/analytics",
  "/admin/audit",
  "/admin/catalog",
  "/admin/catalog/categories",
  "/admin/catalog/media",
  "/admin/catalog/variants",
  "/admin/disputes",
  "/admin/notifications",
  "/admin/orders",
  "/admin/payments",
  "/admin/quotes",
  "/admin/roles",
  "/admin/rules",
  "/admin/settings",
  "/admin/suppliers",
  "/admin/suppliers/offers",
  "/admin/support",
  "/admin/users",
];

test("@public shared layouts do not clip or overlap across responsive widths", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const widths = testInfo.project.name === "mobile-chromium"
    ? [360, 390, 768, 980]
    : [1024, 1180, 1230, 1280, 1366, 1440];

  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await expect(page.locator(".site-header")).toBeVisible();

      const audit = await page.evaluate(() => {
        const tolerance = 1;
        const visible = (element: Element) => {
          const style = window.getComputedStyle(element);
          const box = element.getBoundingClientRect();
          return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
        };
        const rect = (element: Element) => {
          const box = element.getBoundingClientRect();
          return { left: box.left, top: box.top, right: box.right, bottom: box.bottom };
        };
        const intentionallyScrollable = (element: Element) => {
          let ancestor = element.parentElement;
          while (ancestor && ancestor !== document.body) {
            const style = window.getComputedStyle(ancestor);
            if (["auto", "scroll"].includes(style.overflowX) && ancestor.scrollWidth > ancestor.clientWidth + tolerance) {
              return true;
            }
            ancestor = ancestor.parentElement;
          }
          return false;
        };

        const header = document.querySelector<HTMLElement>(".site-header")!;
        const headerChildren = Array.from(header.children).filter(visible);
        const overlaps: string[] = [];
        for (let leftIndex = 0; leftIndex < headerChildren.length; leftIndex += 1) {
          for (let rightIndex = leftIndex + 1; rightIndex < headerChildren.length; rightIndex += 1) {
            const left = rect(headerChildren[leftIndex]);
            const right = rect(headerChildren[rightIndex]);
            const overlapWidth = Math.min(left.right, right.right) - Math.max(left.left, right.left);
            const overlapHeight = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
            if (overlapWidth > tolerance && overlapHeight > tolerance) {
              overlaps.push(`${(headerChildren[leftIndex] as HTMLElement).className} <> ${(headerChildren[rightIndex] as HTMLElement).className}`);
            }
          }
        }

        const clippedHeaderRegions = [".global-search", ".site-header__nav", ".site-header__action"]
          .map(selector => document.querySelector<HTMLElement>(selector))
          .filter((element): element is HTMLElement => Boolean(element) && visible(element!))
          .filter(element => element.scrollWidth > element.clientWidth + tolerance)
          .map(element => ({ className: element.className, clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }));

        const clippedControls = Array.from(document.querySelectorAll<HTMLElement>("a, button, input, select, textarea"))
          .filter(visible)
          .filter(element => !intentionallyScrollable(element))
          .map(element => ({ element, box: rect(element) }))
          .filter(({ box }) => box.left < -tolerance || box.right > window.innerWidth + tolerance)
          .map(({ element, box }) => ({
            tag: element.tagName,
            className: element.className,
            text: (element.textContent || element.getAttribute("aria-label") || "").trim().slice(0, 80),
            left: Math.round(box.left),
            right: Math.round(box.right),
          }));

        const headerBox = rect(header);
        return {
          viewportWidth: window.innerWidth,
          documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
          headerBox,
          overlaps,
          clippedHeaderRegions,
          clippedControls,
        };
      });

      expect.soft(audit.documentOverflow, `${route} at ${width}px document overflow`).toBeLessThanOrEqual(1);
      expect.soft(audit.headerBox.left, `${route} at ${width}px header left`).toBeGreaterThanOrEqual(-1);
      expect.soft(audit.headerBox.right, `${route} at ${width}px header right`).toBeLessThanOrEqual(width + 1);
      expect.soft(audit.overlaps, `${route} at ${width}px header overlap`).toEqual([]);
      expect.soft(audit.clippedHeaderRegions, `${route} at ${width}px clipped header region`).toEqual([]);
      expect.soft(audit.clippedControls, `${route} at ${width}px clipped controls`).toEqual([]);
    }
  }
});

test("@public authenticated account and admin shells stay inside the viewport", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  let role: "customer" | "admin" = "customer";
  await page.route("**/api/**", route => {
    if (new URL(route.request().url()).pathname === "/api/auth/me/") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: role === "admin" ? 1 : 2, username: `${role}-layout-audit`, role }),
      });
    }
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Layout audit fixture" }),
    });
  });

  const widths = testInfo.project.name === "mobile-chromium" ? [390, 768, 980] : [1024, 1230, 1440];
  for (const scenario of [
    { path: "/account", currentRole: "customer" as const, shell: ".account-shell" },
    { path: "/admin", currentRole: "admin" as const, shell: ".admin-app" },
  ]) {
    role = scenario.currentRole;
    for (const width of widths) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(scenario.path, { waitUntil: "domcontentloaded" });
      await expect(page.locator(".site-header--authenticated")).toBeVisible();
      await expect(page.locator(scenario.shell)).toBeVisible();

      const audit = await page.evaluate((shellSelector) => {
        const tolerance = 1;
        const header = document.querySelector<HTMLElement>(".site-header")!;
        const shell = document.querySelector<HTMLElement>(shellSelector)!;
        const visibleChildren = Array.from(header.children).filter(element => {
          const box = element.getBoundingClientRect();
          const style = window.getComputedStyle(element);
          return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
        });
        const overlaps: string[] = [];
        for (let leftIndex = 0; leftIndex < visibleChildren.length; leftIndex += 1) {
          for (let rightIndex = leftIndex + 1; rightIndex < visibleChildren.length; rightIndex += 1) {
            const left = visibleChildren[leftIndex].getBoundingClientRect();
            const right = visibleChildren[rightIndex].getBoundingClientRect();
            if (
              Math.min(left.right, right.right) - Math.max(left.left, right.left) > tolerance &&
              Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top) > tolerance
            ) {
              overlaps.push(`${(visibleChildren[leftIndex] as HTMLElement).className} <> ${(visibleChildren[rightIndex] as HTMLElement).className}`);
            }
          }
        }
        const shellBox = shell.getBoundingClientRect();
        return {
          documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
          headerOverflow: header.scrollWidth - header.clientWidth,
          shellLeft: shellBox.left,
          shellRight: shellBox.right,
          overlaps,
        };
      }, scenario.shell);

      expect.soft(audit.documentOverflow, `${scenario.path} at ${width}px document overflow`).toBeLessThanOrEqual(1);
      expect.soft(audit.headerOverflow, `${scenario.path} at ${width}px header overflow`).toBeLessThanOrEqual(1);
      expect.soft(audit.shellLeft, `${scenario.path} at ${width}px shell left`).toBeGreaterThanOrEqual(-1);
      expect.soft(audit.shellRight, `${scenario.path} at ${width}px shell right`).toBeLessThanOrEqual(width + 1);
      expect.soft(audit.overlaps, `${scenario.path} at ${width}px header overlap`).toEqual([]);
    }
  }

  const representativeWidth = testInfo.project.name === "mobile-chromium" ? 390 : 1230;
  await page.setViewportSize({ width: representativeWidth, height: 900 });
  for (const scenario of [
    { paths: accountRoutes, currentRole: "customer" as const, shell: ".account-shell" },
    { paths: adminRoutes, currentRole: "admin" as const, shell: ".admin-app" },
  ]) {
    role = scenario.currentRole;
    for (const path of scenario.paths) {
      await page.goto(path, { waitUntil: "domcontentloaded" });
      await expect(page.locator(".site-header--authenticated")).toBeVisible();
      await expect(page.locator(scenario.shell)).toBeVisible();
      const bounds = await page.evaluate((shellSelector) => {
        const shell = document.querySelector<HTMLElement>(shellSelector)!;
        const box = shell.getBoundingClientRect();
        return {
          documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
          left: box.left,
          right: box.right,
        };
      }, scenario.shell);
      expect.soft(bounds.documentOverflow, `${path} at ${representativeWidth}px document overflow`).toBeLessThanOrEqual(1);
      expect.soft(bounds.left, `${path} at ${representativeWidth}px shell left`).toBeGreaterThanOrEqual(-1);
      expect.soft(bounds.right, `${path} at ${representativeWidth}px shell right`).toBeLessThanOrEqual(representativeWidth + 1);
    }
  }
});
