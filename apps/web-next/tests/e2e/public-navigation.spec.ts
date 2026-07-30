import { expect, test } from "@playwright/test";

const expectCatalogSnapshot =
  process.env.E2E_EXPECT_CATALOG_SNAPSHOT === "1";

test.beforeEach(async ({ page }) => {
  if (!expectCatalogSnapshot) return;
  await page.route("**/api/**", route =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Live API intentionally unavailable in snapshot E2E" }),
    }),
  );
});

test("@public login exposes separate customer and admin portals", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in to SourceAI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Customer" })).toBeVisible();
  await page.getByRole("button", { name: "Admin / operator" }).click();
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open admin dashboard" })).toBeVisible();
});

test("@public primary customer navigation is keyboard reachable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /Source\s*AI/i }).first()).toBeVisible();
  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  await expect(focused).toBeVisible();
});

test("@public read-only catalog snapshot supports browse, search and detail", async ({ page }) => {
  test.skip(
    !expectCatalogSnapshot,
    "Set E2E_EXPECT_CATALOG_SNAPSHOT=1 with an unavailable API target",
  );
  const mutationRequests: string[] = [];
  page.on("request", request => {
    if (request.method() !== "GET" && new URL(request.url()).pathname.startsWith("/api/")) {
      mutationRequests.push(`${request.method()} ${request.url()}`);
    }
  });

  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Catalog preview" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Browse all 610/ })).toBeVisible();
  const categoryCards = page.locator(".category-strip > a");
  await expect(categoryCards).toHaveCount(12);
  for (const categoryName of [
    "Mobile Accessories",
    "Laptop & PC Accessories",
    "Educational & Academic Tools",
    "Creator & Content Tools",
    "E-commerce Packaging Supplies",
    "Home Organization & Storage",
    "Fashion Accessories",
    "Beauty Tools & Accessories",
    "Kitchen Utility Tools",
    "Office & Desk Accessories",
    "Jewelry, Gems & Precious Metals",
    "Medical Products & Accessories",
  ]) {
    await expect(page.getByRole("link", { name: categoryName, exact: true })).toBeVisible();
  }
  const mobileAccessories = page.getByRole("link", {
    name: /Mobile Accessories/,
  });
  await expect(mobileAccessories).toBeVisible();
  await mobileAccessories.click();
  await expect(page).toHaveURL(/category=mobile-accessories/);
  await expect(page.getByText("12 products", { exact: true })).toBeVisible();

  await page.goto("/");
  const preciousCategory = page.getByRole("link", {
    name: /Jewelry, Gems & Precious Metals/,
  });
  await expect(preciousCategory).toBeVisible();
  await preciousCategory.click();
  await expect(page).toHaveURL(/category=jewelry-gems-precious-metals/);
  await expect(page.getByText("60 products", { exact: true })).toBeVisible();

  await page.goto("/products");
  await expect(page.getByText("610 products", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Quote unavailable" })).toBeDisabled();

  const marketplaceSearch = page.getByRole("search");
  await marketplaceSearch.getByRole("textbox", { name: "Search marketplace" }).fill("iPhone 14");
  await marketplaceSearch.getByRole("button", { name: "Search products" }).click();
  await expect(page).toHaveURL(/\/products\?q=iPhone%2014$/);
  await expect(page.getByText("1 products", { exact: true })).toBeVisible();
  const productCard = page.getByRole("article").filter({ hasText: "iPhone 14" });
  await productCard.getByRole("link", { name: /View product/ }).click();

  await expect(page.getByRole("heading", { name: "iPhone 14", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Request quote unavailable" })).toBeDisabled();

  await page.goto("/quote");
  await expect(page.getByRole("status").filter({ hasText: "Catalog preview" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Request quote unavailable" })).toBeDisabled();
  expect(mutationRequests).toEqual([]);
});
