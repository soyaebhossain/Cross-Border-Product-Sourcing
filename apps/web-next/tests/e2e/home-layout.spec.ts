import { expect, test } from "@playwright/test";

test("@public homepage keeps one professional content frame", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "More than a marketplace." })).toBeVisible();

  const geometry = await page.evaluate(() => {
    const rect = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) throw new Error(`Missing ${selector}`);
      const value = element.getBoundingClientRect();
      return { x: value.x, width: value.width, top: value.top, bottom: value.bottom };
    };
    const main = rect(".market-shell");
    const banner = rect(".decision-banner");
    const footer = rect(".market-footer");
    const footerGrid = rect(".footer-grid");
    const header = rect(".site-header");
    return {
      viewportWidth: window.innerWidth,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      header,
      main,
      banner,
      footer,
      footerGrid,
      bannerFooterGap: footer.top - banner.bottom,
    };
  });

  expect(geometry.overflow).toBeLessThanOrEqual(1);
  expect(geometry.bannerFooterGap).toBeGreaterThanOrEqual(28);
  expect(geometry.bannerFooterGap).toBeLessThanOrEqual(50);

  if (geometry.viewportWidth > 980) {
    expect(Math.abs(geometry.header.x - geometry.main.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(geometry.header.width - geometry.main.width)).toBeLessThanOrEqual(1);
    expect(Math.abs(geometry.footerGrid.x - geometry.main.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(geometry.footerGrid.width - geometry.main.width)).toBeLessThanOrEqual(1);
  }

  const sourceButton = page.getByRole("link", { name: "Start sourcing" });
  const buttonBox = await sourceButton.boundingBox();
  expect(buttonBox!.height).toBeGreaterThanOrEqual(44);
  await expect(page.getByText("Built for trust", { exact: true })).toBeVisible();
});

test("@public product cards keep aligned outlines during interaction", async ({ page }) => {
  await page.goto("/");
  const cards = page.locator(".product-card");
  await expect(cards).toHaveCount(8);

  const before = await cards.evaluateAll(nodes => nodes.map(node => {
    const rect = node.getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  }));
  expect(Math.max(...before.map(item => item.x + item.width))).toBeLessThanOrEqual(page.viewportSize()!.width + 1);

  if (page.viewportSize()!.width > 620) {
    const firstRow = before.slice(0, 4);
    expect(Math.max(...firstRow.map(item => item.y)) - Math.min(...firstRow.map(item => item.y))).toBeLessThanOrEqual(1);
    expect(Math.max(...firstRow.map(item => item.height)) - Math.min(...firstRow.map(item => item.height))).toBeLessThanOrEqual(1);
    const firstCard = cards.first();
    await firstCard.scrollIntoViewIfNeeded();
    const initialBox = await firstCard.boundingBox();
    await firstCard.hover();
    const hoveredBox = await firstCard.boundingBox();
    expect(Math.abs(hoveredBox!.y - initialBox!.y)).toBeLessThanOrEqual(1);
  } else {
    expect(Math.max(...before.map(item => item.x)) - Math.min(...before.map(item => item.x))).toBeLessThanOrEqual(1);
    expect(Math.max(...before.map(item => item.width)) - Math.min(...before.map(item => item.width))).toBeLessThanOrEqual(1);
    const actionHeights = await cards.locator(".card-action").evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
    expect(Math.min(...actionHeights)).toBeGreaterThanOrEqual(44);
  }
});
