import { expect, test, type Page } from "@playwright/test";

const customer = {
  id: 23,
  username: "quote-customer",
  email: "quote-customer@example.com",
  role: "customer",
};

const savedQuotes = [
  {
    id: 41,
    variant_id: 8,
    product_name: "Automatic Blood Pressure Monitor",
    variant_name: "Standard",
    qty: 10,
    country_id: "CN",
    mode: "LOCAL",
    delivery_type: "DOOR",
    status: "approved",
    expires_at: "2099-09-03T10:47:00Z",
    created_at: "2026-08-24T10:47:00Z",
    order_ids: [],
    response: {
      breakdown: {
        product_cost_bdt: "6500.00",
        shipping_bdt: "580.00",
        duty_vat_bdt: "716.00",
        total_bdt: "8684.51",
      },
      eta: { min_days: 7, max_days: 12 },
      ai_explanation: {
        summary_bn: "China offers the strongest balance of landed cost and supplier reliability.",
        advantages: ["Lowest landed cost among eligible routes"],
        risks: ["Supplier lead time should be reconfirmed"],
        recommended_checks: ["Verify warranty and final stock before payment"],
      },
      ai_metadata: {
        source: "ollama-via-n8n",
        model: "qwen3:1.7b",
        automation_available: true,
      },
    },
  },
  {
    id: 42,
    variant_id: 9,
    product_name: "Legacy saved quote",
    variant_name: "Standard",
    qty: 1,
    country_id: "IN",
    mode: "LOCAL",
    delivery_type: "DOOR",
    status: "requested",
    expires_at: "2099-09-04T10:47:00Z",
    created_at: "2026-08-24T11:47:00Z",
    order_ids: [],
    response: {
      breakdown: {
        product_cost_bdt: "1000.00",
        shipping_bdt: "100.00",
        duty_vat_bdt: "50.00",
        total_bdt: "1150.00",
      },
      eta: { min_days: 5, max_days: 9 },
      ai_explanation: { summary_bn: "A legacy explanation with optional fields omitted." },
    },
  },
  {
    id: 43,
    variant_id: 10,
    product_name: "Quote without AI data",
    variant_name: "Standard",
    qty: 1,
    country_id: "SG",
    mode: "LOCAL",
    delivery_type: "DOOR",
    status: "requested",
    expires_at: "2099-09-05T10:47:00Z",
    created_at: "2026-08-24T12:47:00Z",
    order_ids: [],
    response: {
      breakdown: {
        product_cost_bdt: "1200.00",
        shipping_bdt: "120.00",
        duty_vat_bdt: "60.00",
        total_bdt: "1380.00",
      },
      eta: { min_days: 4, max_days: 8 },
    },
  },
];

async function mockSavedQuotesApi(page: Page, quotes: readonly unknown[] = savedQuotes) {
  await page.route("**/api/**", route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(customer) });
    }
    if (pathname === "/api/quote/saved/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(quotes) });
    }
    return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected test request" }) });
  });
}

test("saved quotes show AI decision support and tolerate legacy response shapes", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  await mockSavedQuotesApi(page);

  await page.goto("/account/saved-quotes");
  await expect(page.getByRole("heading", { name: "Saved quotes" })).toBeVisible();
  await expect(page.getByText("AI decision support", { exact: true })).toHaveCount(2);
  await expect(page.getByText("Ollama · qwen3:1.7b", { exact: true })).toBeVisible();
  await expect(page.getByText("Lowest landed cost among eligible routes", { exact: true })).toBeVisible();
  await expect(page.getByText("Supplier lead time should be reconfirmed", { exact: true })).toBeVisible();
  await expect(page.getByText("Verify warranty and final stock before payment", { exact: true })).toBeVisible();

  const legacyCard = page.getByRole("article").filter({ hasText: "Legacy saved quote" });
  await expect(legacyCard.getByText("Source unavailable", { exact: true })).toBeVisible();
  await expect(legacyCard.getByText("No advantages were supplied.", { exact: true })).toBeVisible();
  await expect(legacyCard.getByText("No additional risks were supplied.", { exact: true })).toBeVisible();
  await expect(legacyCard.getByText("No checks were supplied.", { exact: true })).toBeVisible();
  await expect(pageErrors).toEqual([]);
});

test("saved quote cards and AI panels stay inside their containers on desktop and mobile", async ({ page }) => {
  const layoutQuotes = [
    ...savedQuotes,
    {
      ...savedQuotes[0],
      id: 44,
      product_name: "Portable diagnostic and mobility support equipment",
      created_at: "2026-08-24T13:47:00Z",
    },
  ];
  await mockSavedQuotesApi(page, layoutQuotes);

  for (const viewport of [
    { name: "desktop", width: 1440, height: 1000 },
    { name: "compact desktop", width: 1200, height: 900 },
    { name: "mobile", width: 390, height: 844 },
  ]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/account/saved-quotes");
    await expect(page.getByRole("heading", { name: "Saved quotes" })).toBeVisible();
    await expect(page.getByRole("article")).toHaveCount(layoutQuotes.length);

    const audit = await page.evaluate(() => {
      const tolerance = 1;
      const grid = document.querySelector<HTMLElement>(".comparison-grid")!;
      const cards = Array.from(grid.querySelectorAll<HTMLElement>(":scope > .comparison-card"));
      const visible = (element: Element) => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      };
      const horizontalBounds = (element: Element) => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right, width: box.width };
      };
      const gridBounds = horizontalBounds(grid);

      const clippedCards = cards
        .map((card, index) => ({ index, bounds: horizontalBounds(card) }))
        .filter(({ bounds }) => bounds.left < gridBounds.left - tolerance || bounds.right > gridBounds.right + tolerance);

      const overflowingCards = cards
        .map((card, index) => ({ index, overflow: card.scrollWidth - card.clientWidth }))
        .filter(({ overflow }) => overflow > tolerance);

      const clippedAiPanels = cards.flatMap((card, cardIndex) => {
        const cardBounds = horizontalBounds(card);
        return Array.from(card.querySelectorAll<HTMLElement>(".workspace-ai")).flatMap((panel, panelIndex) => {
          const panelBounds = horizontalBounds(panel);
          const overflowingDescendants = [panel, ...Array.from(panel.querySelectorAll<HTMLElement>("*"))]
            .filter(visible)
            .map(element => ({
              className: element.className,
              text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 70),
              bounds: horizontalBounds(element),
              overflow: element.scrollWidth - element.clientWidth,
            }))
            .filter(item => (
              item.bounds.left < panelBounds.left - tolerance ||
              item.bounds.right > panelBounds.right + tolerance ||
              item.overflow > tolerance
            ));

          if (
            panelBounds.left < cardBounds.left - tolerance ||
            panelBounds.right > cardBounds.right + tolerance ||
            overflowingDescendants.length > 0
          ) {
            return [{ cardIndex, panelIndex, cardBounds, panelBounds, overflowingDescendants }];
          }
          return [];
        });
      });

      return {
        documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
        gridOverflow: grid.scrollWidth - grid.clientWidth,
        clippedCards,
        overflowingCards,
        clippedAiPanels,
      };
    });

    expect.soft(audit.documentOverflow, `${viewport.name}: document horizontal overflow`).toBeLessThanOrEqual(1);
    expect.soft(audit.gridOverflow, `${viewport.name}: quote grid horizontal overflow`).toBeLessThanOrEqual(1);
    expect.soft(audit.clippedCards, `${viewport.name}: quote cards clipped by grid`).toEqual([]);
    expect.soft(audit.overflowingCards, `${viewport.name}: quote card content overflow`).toEqual([]);
    expect.soft(audit.clippedAiPanels, `${viewport.name}: AI panel content clipped or overflowing`).toEqual([]);
  }
});
