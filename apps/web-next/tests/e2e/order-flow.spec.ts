import { expect, test, type Page } from "@playwright/test";

const product = {
  id: 800,
  name: "Order Flow Lamp",
  slug: "order-flow-lamp",
  model: "OF-800",
  description: "Deterministic product for the ordering path.",
  image: null,
  category: { id: 80, name: "Lighting", slug: "lighting" },
  default_variant_id: 801,
  variants: [{ id: 801, sku: "OF-800-STD", variant_name: "Standard", weight_kg: "1.00", length_cm: "10.00", width_cm: "10.00", height_cm: "10.00" }],
};

const quote = {
  offers_top: [{ id: 1, seller: "Lamp Works", price_origin: "10.00", currency: "USD", stock: 50, rating: "4.6", moq: 1 }],
  selected_offer_id: 1,
  breakdown: {
    product_cost_bdt: "2400.00", origin_price_bdt: "2400.00", shipping_bdt: "300.00", customs_duty_bdt: "270.00",
    vat_tax_bdt: "135.00", handling_charge_bdt: "0.00", other_import_cost_bdt: "0.00", duty_vat_bdt: "405.00",
    service_fee_bdt: "0.00", total_bdt: "3105.00", advance_bdt: "1863.00", remaining_bdt: "1242.00",
  },
  eta: { min_days: 5, max_days: 9 },
};

async function mockApi(page: Page, options: { signedIn: boolean; requests: string[] }) {
  await page.addInitScript(() => {
    if (window.localStorage.getItem("sourceai-locale") === null) window.localStorage.setItem("sourceai-locale", "en");
  });
  await page.route("**/api/**", async route => {
    const pathname = new URL(route.request().url()).pathname;
    const json = (status: number, body: unknown) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (pathname === "/api/products/") return json(200, [product]);
    if (pathname === "/api/countries/") return json(200, [{ id: 1, code: "CN", name: "China" }]);
    if (pathname === "/api/auth/session/") return json(200, { authenticated: false, can_refresh: false, user: null });
    if (pathname === "/api/quote/ai-explanation/") {
      options.requests.push(route.request().postData() || "");
      return json(200, quote);
    }
    if (pathname === "/api/quote/save/") return options.signedIn ? json(201, { id: 77 }) : json(401, { detail: "Authentication required" });
    return json(503, { detail: "Unexpected test request" });
  });
}

test("an order link calculates the cost without another click and shows the ordering steps", async ({ page }) => {
  const requests: string[] = [];
  await mockApi(page, { signedIn: false, requests });

  await page.goto("/quote?variant=801&qty=2&country=CN&auto=1");

  await expect(page.locator(".quote-summary")).toContainText("3,105.00");
  expect(requests).toHaveLength(1);
  expect(JSON.parse(requests[0])).toMatchObject({ variant_id: 801, qty: 2, country: "CN" });
  await expect(page.locator(".order-steps__item--current")).toContainText("See total cost");
  await expect(page.getByRole("button", { name: "Continue to order" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save for comparison" })).toBeVisible();
});

test("continuing to order while signed out asks for sign-in and returns to the same quote", async ({ page }) => {
  await mockApi(page, { signedIn: false, requests: [] });
  await page.goto("/quote?variant=801&qty=2&country=CN&auto=1");

  await page.getByRole("button", { name: "Continue to order" }).click();

  await page.waitForURL(/\/login\?next=/);
  const next = new URL(page.url()).searchParams.get("next");
  expect(next).toBe("/quote?variant=801&qty=2&country=CN&mode=LOCAL&auto=1");
});

test("continuing to order while signed in saves the quote and opens checkout", async ({ page }) => {
  await mockApi(page, { signedIn: true, requests: [] });
  await page.goto("/quote?variant=801&qty=2&country=CN&auto=1");

  await page.getByRole("button", { name: "Continue to order" }).click();

  await page.waitForURL(/\/account\/saved-quotes\/77\/order$/);
});
