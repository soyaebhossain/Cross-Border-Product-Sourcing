import { expect, test, type Page } from "@playwright/test";

const apiBase = process.env.E2E_API_BASE_URL || process.env.API_BASE_URL || "http://127.0.0.1:8001";
const customerIdentifier = process.env.E2E_CUSTOMER_IDENTIFIER;
const customerPassword = process.env.E2E_CUSTOMER_PASSWORD;
const adminIdentifier = process.env.E2E_ADMIN_IDENTIFIER;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;

async function login(page: Page, portal: "Customer" | "Admin / operator", identifier: string, password: string) {
  await page.goto(portal === "Customer" ? "/login" : "/login?portal=admin");
  await page.getByRole("button", { name: portal }).click();
  await page.getByLabel("Username, email or phone").fill(identifier);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: portal === "Customer" ? "Sign in securely" : "Open admin dashboard" }).click();
}

test.describe("@roles live role-routing contract", () => {
  test.beforeEach(async ({ request }) => {
    const health = await request.get(`${apiBase}/api/health`);
    test.skip(!health.ok(), `Live backend is required at ${apiBase}`);
  });

  test("catalog requests remain on the storefront origin", async ({ page, baseURL }) => {
    const storefrontOrigin = new URL(baseURL!).origin;
    const apiRequests: string[] = [];
    page.on("request", request => {
      if (new URL(request.url()).pathname.startsWith("/api/")) {
        apiRequests.push(request.url());
      }
    });

    const [catalogResponse] = await Promise.all([
      page.waitForResponse(response => new URL(response.url()).pathname === "/api/catalog/browse/"),
      page.goto("/products"),
    ]);
    expect(catalogResponse.ok()).toBe(true);
    const catalog = (await catalogResponse.json()) as { total: number };
    expect(catalog.total).toBeGreaterThan(0);
    await expect(page.getByText(`${catalog.total} products`, { exact: true })).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Catalog preview" })).toHaveCount(0);
    expect(apiRequests.length).toBeGreaterThan(0);
    expect(apiRequests.every(url => new URL(url).origin === storefrontOrigin)).toBe(true);
  });

  test("noncanonical API paths never redirect away from the storefront", async ({ request }) => {
    const responses = await Promise.all([
      request.get("/api/categories", { maxRedirects: 0 }),
      request.get("/api/health/", { maxRedirects: 0 }),
      request.post("/api/auth/login", { data: {}, maxRedirects: 0 }),
    ]);

    for (const response of responses) {
      expect(response.status()).toBe(404);
      expect(response.headers().location).toBeUndefined();
    }
  });

  test("customer lands in customer account and is kept out of admin", async ({ page }) => {
    test.skip(!customerIdentifier || !customerPassword, "Set E2E_CUSTOMER_IDENTIFIER and E2E_CUSTOMER_PASSWORD");
    await login(page, "Customer", customerIdentifier!, customerPassword!);
    await expect(page).toHaveURL(/\/account(?:\/|$)/);
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/(?:account|login)(?:\/|\?|$)/);
  });

  test("administrator lands in control center and is kept out of customer account", async ({ page }) => {
    test.skip(!adminIdentifier || !adminPassword, "Set E2E_ADMIN_IDENTIFIER and E2E_ADMIN_PASSWORD");
    await login(page, "Admin / operator", adminIdentifier!, adminPassword!);
    await expect(page).toHaveURL(/\/admin(?:\/|$)/);
    await expect(page.getByRole("navigation", { name: "Admin navigation" })).toBeVisible();
    await page.goto("/account");
    await expect(page).toHaveURL(/\/admin(?:\/|$)/);
  });
});
