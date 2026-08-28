import { expect, test, type Page } from "@playwright/test";

const product = {
  id: 901,
  name: "Regression Test Product",
  slug: "regression-test-product",
  model: "RTP-901",
  description: "Deterministic catalog fixture for focused UX regression coverage.",
  image: null,
  image_alt: "Regression Test Product",
  image_source: "illustrative",
  image_verified: false,
  category: {
    id: 90,
    name: "Test Supplies",
    slug: "test-supplies",
  },
  default_variant_id: 9_001,
  variants: [{
    id: 9_001,
    sku: "RTP-901-STD",
    variant_name: "Standard",
    weight_kg: "1.00",
  }],
  market: {
    min_price: 12.5,
    currency: "USD",
    countries: ["CN"],
    supplier_count: 1,
    min_delivery_days: 7,
    max_rating: 4.7,
    risk_level: "Low",
  },
};

const basketItem = {
  key: "901:9001:CN",
  productId: product.id,
  productName: product.name,
  productSlug: product.slug,
  productModel: product.model,
  categoryName: product.category.name,
  imageSrc: null,
  imageAlt: product.image_alt,
  imageKind: "illustrative",
  variantId: product.default_variant_id,
  variantName: "Standard",
  variants: product.variants,
  quantity: 1,
  moq: 1,
  countryCode: "CN",
  availableCountries: ["CN"],
  estimatedUnitPrice: product.market.min_price,
  currency: product.market.currency,
  deliveryMinDays: product.market.min_delivery_days,
  riskLevel: product.market.risk_level,
  supplierRating: product.market.max_rating,
  supplierLabel: "Supplier selection pending",
  catalogPreview: false,
};

async function seedBasket(page: Page, quantity: number) {
  await page.addInitScript(({ item, seededQuantity }) => {
    window.localStorage.setItem(
      "sourceai-sourcing-basket-v1",
      JSON.stringify([{ ...item, quantity: seededQuantity }]),
    );
  }, { item: basketItem, seededQuantity: quantity });
}

async function mockQuoteCatalog(page: Page) {
  await page.route("**/api/products/", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([product]),
  }));
  await page.route("**/api/countries/", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([{ code: "CN", name: "China" }]),
  }));
}

test("quote and basket quantities cannot exceed 100,000", async ({ page }) => {
  await mockQuoteCatalog(page);
  await page.goto("/quote?variant=9001&country=CN&qty=250000");

  const quoteQuantity = page.getByRole("spinbutton");
  await expect(quoteQuantity).toHaveAttribute("max", "100000");
  await expect(quoteQuantity).toHaveValue("100000");

  await seedBasket(page, 250_000);
  await page.goto("/sourcing-basket");

  const basketQuantity = page.getByRole("spinbutton", {
    name: `Quantity: ${product.name}`,
  });
  await expect(basketQuantity).toHaveAttribute("max", "100000");
  await expect(basketQuantity).toHaveValue("100000");
  await expect(page.getByRole("button", {
    name: `Quantity: ${product.name}: increase`,
  })).toBeDisabled();

  await basketQuantity.fill("100001");
  await expect(basketQuantity).toHaveValue("100000");
});

test("compare query IDs are de-duplicated and preserve one page heading", async ({ page }) => {
  await page.goto("/compare?products=1,1,2,2,0,-3,not-a-number");

  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1, name: "Compare products" })).toBeVisible();
  const comparedProducts = page.locator(".comparison-table__product");
  await expect(comparedProducts).toHaveCount(2);
  const names = await comparedProducts.locator("strong").allTextContents();
  expect(new Set(names).size).toBe(names.length);

  await page.goto("/compare?products=invalid");
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByRole("heading", {
    level: 2,
    name: "No products selected for comparison",
  })).toBeVisible();
});

test("catalog uses singular product grammar for one result", async ({ page }) => {
  await page.route("**/api/catalog/browse/**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      items: [product],
      total: 1,
      page: 1,
      page_size: 24,
      pages: 1,
    }),
  }));
  await page.route("**/api/categories/", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: "[]",
  }));
  await page.route("**/api/countries/", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: "[]",
  }));

  await page.goto("/products?q=Regression%20Test%20Product");
  await expect(page.getByText("1 product", { exact: true })).toBeVisible();
  await expect(page.getByText("1 products", { exact: true })).toHaveCount(0);
});

test("basket explains authentication recovery without discarding items", async ({ page }) => {
  let quotedQuantity: number | null = null;
  await seedBasket(page, 2);
  await page.route("**/api/quote/ai-explanation/", async route => {
    const payload = route.request().postDataJSON() as { qty?: number };
    quotedQuantity = payload.qty ?? null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ breakdown: {} }),
    });
  });
  await page.route("**/api/quote/save/", route => route.fulfill({
    status: 401,
    contentType: "application/json",
    body: JSON.stringify({ detail: "Authentication required" }),
  }));
  await page.route("**/api/auth/refresh/", route => route.fulfill({
    status: 401,
    contentType: "application/json",
    body: JSON.stringify({ detail: "No active session" }),
  }));

  await page.goto("/sourcing-basket");
  await page.getByRole("button", { name: "Request quote", exact: true }).click();

  const recovery = page.getByRole("status").filter({
    hasText: "Your quote was calculated, but you need to sign in to save it.",
  });
  await expect(recovery).toContainText("Your basket remains saved in this browser.");
  await expect(recovery.getByRole("link", { name: "Sign in to save the quote" }))
    .toHaveAttribute("href", "/login");
  await expect(page.getByRole("heading", { name: product.name })).toBeVisible();
  expect(quotedQuantity).toBe(2);

  const storedItems = await page.evaluate(() => JSON.parse(
    window.localStorage.getItem("sourceai-sourcing-basket-v1") || "[]",
  ) as unknown[]);
  expect(storedItems).toHaveLength(1);
});

test("checkout blocks payment until default shipping and billing addresses exist", async ({ page }) => {
  const savedQuote = {
    id: 5,
    variant_id: product.default_variant_id,
    product_name: product.name,
    variant_name: "Standard",
    country_id: "CN",
    mode: "LOCAL",
    delivery_type: "DOOR",
    qty: 1,
    status: "requested",
    expires_at: "2099-01-01T00:00:00Z",
    order_ids: [],
    response: {
      breakdown: {
        total_bdt: "5000.00",
        advance_bdt: "3000.00",
        remaining_bdt: "2000.00",
      },
    },
  };
  await page.route("**/api/**", route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me/") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 27, username: "buyer", role: "customer" }),
      });
    }
    if (pathname === "/api/quote/saved/5/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(savedQuote) });
    }
    if (pathname === "/api/account/addresses/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    }
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Checkout test fixture" }),
    });
  });

  await page.goto("/account/saved-quotes/5/order");

  await expect(page.getByRole("heading", { name: "Confirm sourcing order" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Delivery addresses required" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Add addresses →" })).toHaveAttribute("href", "/account/profile");
  await expect(page.getByRole("button", { name: "Confirm and place order" })).toBeDisabled();
});
