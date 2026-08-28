import { createServer, type Server } from "node:http";
import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const BENGALI_SCRIPT = /[\u0980-\u09ff]/u;
const productSlug = "locale-ai-test-product";
const productVariantId = 501;

test.describe.configure({ mode: "serial" });

const product = {
  id: 500,
  name: "Locale Test Product",
  slug: productSlug,
  model: "LT-500",
  description: "A deterministic product fixture for locale regression coverage.",
  image: null,
  category: { id: 50, name: "Test equipment", slug: "test-equipment" },
  default_variant_id: productVariantId,
  variants: [{
    id: productVariantId,
    sku: "LT-500-STD",
    variant_name: "Standard",
    weight_kg: "1.00",
    length_cm: "10.00",
    width_cm: "10.00",
    height_cm: "10.00",
  }],
};

const englishExplanation = {
  summary: "Malaysia has the best verified balance of cost, delivery, and risk.",
  // Deliberately conflicting legacy data: an English UI must prefer `summary`.
  summary_bn: "মালয়েশিয়া থেকে সোর্সিং করার বাংলা পুরোনো সারাংশ।",
  language: "en",
  advantages: ["The landed cost is calculated by the server."],
  risks: ["Supplier capacity must be reconfirmed."],
  missing_information: ["Final carrier documentation is pending."],
  recommended_checks: ["Verify stock before payment."],
  confidence: 0.82,
  human_review_required: false,
};

const bengaliExplanation = {
  summary: "মালয়েশিয়া থেকে সোর্সিং করলে যাচাইকৃত খরচ ও ঝুঁকির ভারসাম্য ভালো।",
  summary_bn: "মালয়েশিয়া থেকে সোর্সিং করলে যাচাইকৃত খরচ ও ঝুঁকির ভারসাম্য ভালো।",
  language: "bn",
  advantages: ["ল্যান্ডেড কস্ট সার্ভারে হিসাব করা হয়েছে।"],
  risks: ["সাপ্লায়ারের সক্ষমতা আবার যাচাই করতে হবে।"],
  missing_information: ["চূড়ান্ত ক্যারিয়ার নথি পাওয়া যায়নি।"],
  recommended_checks: ["পেমেন্টের আগে স্টক যাচাই করুন।"],
  confidence: 0.82,
  human_review_required: false,
};

const recommendationBase = {
  product: {
    id: product.id,
    name: product.name,
    slug: product.slug,
    variant_id: productVariantId,
    variant_name: "Standard",
  },
  priority: "balanced",
  delivery_type: "DOOR",
  qty: 1,
  methodology: {
    type: "weighted-score",
    summary: "Server-calculated sourcing score.",
    weights: { price: "0.35", quality: "0.20", delivery: "0.15", reliability: "0.15", risk: "0.15" },
  },
  recommendations: [{
    rank: 1,
    country: { id: 1, code: "MY", name: "Malaysia" },
    mode: "LOCAL",
    score: "81.00",
    estimated_total_bdt: "10000.00",
    estimated_shipping_bdt: "1000.00",
    estimated_duty_vat_bdt: "1000.00",
    estimated_service_fee_bdt: "500.00",
    eta: { min_days: 5, max_days: 8 },
    quality_score: "8.20",
    reliability_score: "8.40",
    risk_level: "Low",
    risk_score: "2.00",
    advantages: ["Verified supplier"],
    weaknesses: [],
    selected_offer: {
      id: 901,
      seller_name: "Locale Supplier",
      price_origin: "75.00",
      currency: "USD",
      stock: 100,
      moq: 1,
      source_url: null,
    },
    reason: "Balanced cost, delivery, and supplier reliability.",
  }],
  data_gaps: [],
};

const quoteBreakdown = {
  product_cost_bdt: "6500.00",
  origin_price_bdt: "6500.00",
  shipping_bdt: "580.00",
  customs_duty_bdt: "58.00",
  vat_tax_bdt: "58.00",
  handling_charge_bdt: "1240.60",
  other_import_cost_bdt: "0.00",
  duty_vat_bdt: "716.00",
  service_fee_bdt: "1240.60",
  total_bdt: "8684.51",
  advance_bdt: "2171.13",
  remaining_bdt: "6513.38",
};

function explanationFor(language: unknown) {
  return language === "bn" ? bengaliExplanation : englishExplanation;
}

function recommendationResponse(language: unknown) {
  return {
    ...recommendationBase,
    ai_explanation: explanationFor(language),
    ai_metadata: {
      source: "ollama-via-n8n",
      model: "qwen3:1.7b",
      automation_available: true,
      monetary_calculations_are_deterministic: true,
    },
  };
}

function quoteResponse(language: unknown) {
  return {
    breakdown: quoteBreakdown,
    eta: { min_days: 5, max_days: 8 },
    ai_explanation: explanationFor(language),
    ai_metadata: {
      source: "ollama-via-n8n",
      model: "qwen3:1.7b",
      automation_available: true,
      monetary_calculations_are_deterministic: true,
    },
  };
}

function savedQuote(language: "en" | "bn") {
  return {
    id: 801,
    variant_id: productVariantId,
    product_name: product.name,
    variant_name: "Standard",
    qty: 1,
    country_id: "MY",
    mode: "LOCAL",
    delivery_type: "DOOR",
    status: "requested",
    expires_at: "2099-09-03T10:47:00Z",
    created_at: "2026-08-24T10:47:00Z",
    order_ids: [],
    response: quoteResponse(language),
  };
}

async function jsonBody(route: Route) {
  return JSON.parse(route.request().postData() || "{}") as Record<string, unknown>;
}

async function setStoredLocale(page: Page, locale: "en" | "bn") {
  await page.addInitScript((value) => {
    if (window.localStorage.getItem("sourceai-locale") === null) {
      window.localStorage.setItem("sourceai-locale", value);
    }
  }, locale);
}

async function expectNoBengali(locator: Locator) {
  await expect(locator).toBeVisible();
  expect(await locator.innerText()).not.toMatch(BENGALI_SCRIPT);
}

async function expectBengali(locator: Locator) {
  await expect(locator).toBeVisible();
  expect(await locator.innerText()).toMatch(BENGALI_SCRIPT);
}

async function mockQuoteApis(page: Page, requestedLanguages: unknown[]) {
  await page.route("**/api/**", async route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/products/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([product]) });
    }
    if (pathname === "/api/countries/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ id: 1, code: "MY", name: "Malaysia" }]) });
    }
    if (pathname === "/api/quote/ai-explanation/") {
      const body = await jsonBody(route);
      requestedLanguages.push(body.language);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quoteResponse(body.language)) });
    }
    return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected test request" }) });
  });
}

function productSelect(page: Page) {
  return page.locator(".form-field").filter({ has: page.getByText("Product", { exact: true }) }).locator("select");
}

let productApiServer: Server | undefined;

test.beforeAll(async () => {
  if (process.env.PLAYWRIGHT_BASE_URL || process.env.API_BASE_URL) return;

  productApiServer = createServer((request, response) => {
    response.setHeader("content-type", "application/json");
    if (request.method === "GET" && request.url === `/api/products/${productSlug}/`) {
      response.statusCode = 200;
      response.end(JSON.stringify(product));
      return;
    }
    if (request.method === "POST" && request.url === "/api/recommendations/cheapest-country/") {
      response.statusCode = 200;
      response.end(JSON.stringify(recommendationBase));
      return;
    }
    response.statusCode = 503;
    response.end(JSON.stringify({ detail: "Unavailable in locale fixture" }));
  });

  await new Promise<void>((resolve, reject) => {
    productApiServer!.once("error", reject);
    productApiServer!.listen(8001, "127.0.0.1", resolve);
  });
});

test.afterAll(async () => {
  if (!productApiServer) return;
  await new Promise<void>((resolve, reject) => productApiServer!.close(error => error ? reject(error) : resolve()));
});

test("English quote AI explanation never renders the conflicting Bengali legacy summary", async ({ page }) => {
  const requestedLanguages: unknown[] = [];
  await setStoredLocale(page, "en");
  await mockQuoteApis(page, requestedLanguages);

  await page.goto(`/quote?variant=${productVariantId}&country=MY`);
  await expect(productSelect(page)).toHaveValue(String(product.id));
  await page.getByRole("button", { name: "Request quote" }).click();

  const explanation = page.locator("article[aria-labelledby='ai-explanation-title']");
  await expect(explanation).toContainText(englishExplanation.summary);
  await expectNoBengali(explanation);
  expect(requestedLanguages).toEqual(["en"]);
});

test("Bangla quote requests and renders a Bangla AI explanation", async ({ page }) => {
  const requestedLanguages: unknown[] = [];
  await setStoredLocale(page, "bn");
  await mockQuoteApis(page, requestedLanguages);

  await page.goto(`/quote?variant=${productVariantId}&country=MY`);
  await expect(productSelect(page)).toHaveValue(String(product.id));
  await page.getByRole("button", { name: "Request quote" }).click();

  const explanation = page.locator("article[aria-labelledby='ai-explanation-title']");
  await expect(explanation).toContainText(bengaliExplanation.summary);
  await expectBengali(explanation);
  await expect.poll(() => requestedLanguages.at(-1)).toBe("bn");
});

test("saved AI explanations follow the active locale instead of the legacy summary field", async ({ page }) => {
  let responseLanguage: "en" | "bn" = "en";
  await setStoredLocale(page, "en");
  await page.route("**/api/**", route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: 23, username: "locale-customer", email: "locale@example.com", role: "customer" }) });
    }
    if (pathname === "/api/quote/saved/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([savedQuote(responseLanguage)]) });
    }
    return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected test request" }) });
  });

  await page.goto("/account/saved-quotes");
  const explanation = page.locator(".saved-quote-card .workspace-ai");
  await expect(explanation).toContainText(englishExplanation.summary);
  await expectNoBengali(explanation);

  responseLanguage = "bn";
  await page.evaluate(() => window.localStorage.setItem("sourceai-locale", "bn"));
  await page.reload();
  await expect(explanation).toContainText(bengaliExplanation.summary);
  await expectBengali(explanation);
});

test("product recommendation AI explanation sends and honors the active locale", async ({ page }) => {
  test.skip(Boolean(process.env.PLAYWRIGHT_BASE_URL || process.env.API_BASE_URL), "The deterministic product fixture requires Playwright's local API target.");
  const requestedLanguages: unknown[] = [];
  await setStoredLocale(page, "en");
  await page.route("**/api/recommendations/cheapest-country/ai-explanation/", async route => {
    const body = await jsonBody(route);
    requestedLanguages.push(body.language);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(recommendationResponse(body.language)) });
  });

  await page.goto(`/products/${productSlug}`);
  const explanation = page.locator(".workspace-ai");
  await expect(explanation).toContainText(englishExplanation.summary);
  await expectNoBengali(explanation);
  await expect.poll(() => requestedLanguages.at(-1)).toBe("en");

  await page.getByRole("button", { name: "Switch to Bangla" }).click();
  await expect.poll(() => requestedLanguages.at(-1)).toBe("bn");
  await expect(explanation).toContainText(bengaliExplanation.summary);
  await expectBengali(explanation);
});
