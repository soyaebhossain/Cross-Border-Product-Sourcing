import { expect, test, type Page } from "@playwright/test";

const product = {
  id: 700,
  name: "Pricing Fixture Lamp",
  slug: "pricing-fixture-lamp",
  model: "PF-700",
  description: "Deterministic product for price provenance coverage.",
  image: null,
  category: { id: 70, name: "Lighting", slug: "lighting" },
  default_variant_id: 701,
  variants: [{ id: 701, sku: "PF-700-STD", variant_name: "Standard", weight_kg: "1.00", length_cm: "10.00", width_cm: "10.00", height_cm: "10.00" }],
};

const verifiedAt = "2026-11-11T19:17:30+00:00";

function quoteResponse(status: "verified" | "indicative") {
  const offerFresh = status === "verified";
  return {
    offers_top: [{ id: 1, seller: "Lamp Works", price_origin: "10.00", currency: "USD", stock: 50, rating: "4.6", moq: 1 }],
    selected_offer_id: 1,
    breakdown: {
      product_cost_bdt: "1246.11", origin_price_bdt: "1246.11", shipping_bdt: "300.00", customs_duty_bdt: "154.61",
      vat_tax_bdt: "77.31", handling_charge_bdt: "0.00", other_import_cost_bdt: "0.00", duty_vat_bdt: "231.92",
      service_fee_bdt: "0.00", total_bdt: "1778.03", advance_bdt: "1066.82", remaining_bdt: "711.21",
    },
    eta: { min_days: 5, max_days: 9 },
    pricing: {
      status,
      calculated_at: "2026-11-11T19:21:00+00:00",
      stale_components: offerFresh ? [] : ["supplier_offer"],
      components: [
        {
          component: "supplier_offer", source: offerFresh ? "admin" : "seeded", reference: "https://supplier.example.com/lamp",
          verified_at: offerFresh ? verifiedAt : null, valid_until: null, max_age_hours: 168, age_hours: offerFresh ? 1 : null,
          fresh: offerFresh, stale_reasons: offerFresh ? [] : ["unverified"], currency: "USD", price_origin: "10.00",
        },
        {
          component: "fx_rate", source: "api", reference: "ExchangeRate-API (open.er-api.com)", verified_at: verifiedAt,
          valid_until: null, max_age_hours: 48, age_hours: 1, fresh: true, stale_reasons: [], currency: "USD", rate_to_bdt: "124.61068300",
        },
        {
          component: "freight", source: "admin", reference: null, verified_at: verifiedAt, valid_until: null,
          max_age_hours: 720, age_hours: 1, fresh: true, stale_reasons: [], method: "AIR",
        },
        {
          component: "customs_duty", source: "admin", reference: null, verified_at: verifiedAt, valid_until: null,
          max_age_hours: 8760, age_hours: 1, fresh: true, stale_reasons: [], percent: "10.00",
        },
      ],
    },
    ai_explanation: {
      summary: "China is the top option.", summary_bn: "China is the top option.", language: "en",
      advantages: [], risks: [], missing_information: [], recommended_checks: [], confidence: null, human_review_required: !offerFresh,
    },
    ai_metadata: { source: "deterministic-fallback", model: null, automation_available: false, monetary_calculations_are_deterministic: true },
  };
}

async function mockQuote(page: Page, status: "verified" | "indicative") {
  await page.addInitScript(() => {
    if (window.localStorage.getItem("sourceai-locale") === null) window.localStorage.setItem("sourceai-locale", "en");
  });
  await page.route("**/api/**", route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/products/") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([product]) });
    if (pathname === "/api/countries/") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ id: 1, code: "CN", name: "China" }]) });
    if (pathname === "/api/quote/ai-explanation/") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteResponse(status)) });
    return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected test request" }) });
  });
  await page.goto(`/quote?variant=${product.default_variant_id}&country=CN`);
  await page.getByRole("button", { name: "Request quote" }).click();
  return page.locator("article[aria-labelledby='pricing-provenance-title']");
}

test("indicative quote shows which price inputs are unverified and credits the live FX source", async ({ page }) => {
  const panel = await mockQuote(page, "indicative");

  await expect(panel.getByRole("heading", { name: "Indicative prices" })).toBeVisible();
  await expect(panel).toContainText("Re-verify before ordering");
  await expect(panel).toContainText("recalculates the landed cost with current data");
  await expect(panel.locator("li").filter({ hasText: "Supplier price" })).toContainText("Never verified");
  await expect(panel.locator("li").filter({ hasText: "Exchange rate" })).toContainText("1 USD = ৳124.6107");
  await expect(panel.locator("li").filter({ hasText: "Exchange rate" })).toContainText("Live feed");
  await expect(panel.getByRole("link", { name: "Rates By Exchange Rate API" })).toHaveAttribute("href", "https://www.exchangerate-api.com");
});

test("fully verified quote is labelled as verified", async ({ page }) => {
  const panel = await mockQuote(page, "verified");

  await expect(panel.getByRole("heading", { name: "All prices recently verified" })).toBeVisible();
  await expect(panel).not.toContainText("Re-verify before ordering");
  await expect(panel.locator("li").filter({ hasText: "Supplier price" })).toContainText("Within 7 days limit");
});
