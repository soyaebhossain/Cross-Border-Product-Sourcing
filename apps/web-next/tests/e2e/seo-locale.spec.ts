import { expect, test } from "@playwright/test";

test.beforeEach(async ({ context, page }) => {
  await context.clearCookies();
  await page.goto("/");
  await page.evaluate(() => window.localStorage.removeItem("sourceai-locale"));
});

test("selected locale persists in storage, cookie, DOM, and server-rendered html", async ({ context, page }) => {
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");

  await page.locator("button.locale-toggle:visible").first().click();
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("sourceai-locale"))).toBe("bn");
  await expect.poll(async () => {
    const localeCookie = (await context.cookies()).find(cookie => cookie.name === "sourceai-locale");
    return localeCookie?.value;
  }).toBe("bn");

  const response = await page.reload();
  expect(response).not.toBeNull();
  const servedHtml = await response!.text();
  expect(servedHtml).toMatch(/<html[^>]*lang="bn"/i);
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
});

test("key public pages expose unique headings, titles, descriptions, and canonicals", async ({ page }) => {
  const pages = [
    { path: "/", title: /SourceAI \| Explainable Sourcing Decision Support/, canonical: "/" },
    { path: "/products", title: /Global Product Catalog \| SourceAI/, canonical: "/products" },
    { path: "/categories", title: /Product Categories \| SourceAI/, canonical: "/categories" },
    { path: "/quote", title: /Request a Sourcing Quote \| SourceAI/, canonical: "/quote" },
  ];

  for (const entry of pages) {
    await page.goto(entry.path);
    await expect(page).toHaveTitle(entry.title);
    await expect(page.locator("main h1")).toHaveCount(1);
    const description = await page.locator('meta[name="description"]').getAttribute("content");
    expect(description?.trim().length).toBeGreaterThanOrEqual(20);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(new URL(canonical!).pathname).toBe(entry.canonical);
  }
});

test("product detail metadata is specific and account entry pages are not indexed", async ({ page }) => {
  await page.goto("/products/iphone-14");
  await expect(page).toHaveTitle(/iPhone 14 \| SourceAI/);
  await expect(page.locator("main h1")).toHaveCount(1);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/products\/iphone-14$/);

  await page.goto("/login");
  await expect(page).toHaveTitle(/Secure Sign In \| SourceAI/);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
});

test("crawler and install metadata routes are available", async ({ request }) => {
  const robots = await request.get("/robots.txt");
  expect(robots.ok()).toBeTruthy();
  expect(await robots.text()).toContain("Sitemap:");

  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.ok()).toBeTruthy();
  expect(await sitemap.text()).toContain("/products");

  const manifest = await request.get("/manifest.webmanifest");
  expect(manifest.ok()).toBeTruthy();
  expect((await manifest.json()).short_name).toBe("SourceAI");
});
