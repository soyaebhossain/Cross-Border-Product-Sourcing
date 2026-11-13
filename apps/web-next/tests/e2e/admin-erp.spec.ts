import { expect, test, type Page } from "@playwright/test";

type Receipt = { id: number; received_qty: number; accepted_qty: number; rejected_qty: number; qc_note: string | null; received_at: string };
type Payment = { id: number; amount_origin: string; currency: string; fx_rate_to_bdt: string; amount_bdt: string; method: string; reference: string | null; paid_at: string; status: "POSTED" | "REVERSED" };

const FX = 125;
const TOTAL = 250;
const ORDERED = 20;
const NEXT_STATUSES: Record<string, string[]> = {
  DRAFT: ["SENT", "CANCELLED"],
  SENT: ["CONFIRMED", "CANCELLED"],
  CONFIRMED: ["CANCELLED"],
  RECEIVED: ["CLOSED"],
  CLOSED: [],
  CANCELLED: [],
};

/** A purchase order held in memory, answering the admin API the way the service does. */
function createBackOffice() {
  const state = {
    exists: false,
    status: "DRAFT",
    orderStatus: "CONFIRMED",
    receipts: [] as Receipt[],
    payments: [] as Payment[],
    requests: [] as Array<{ path: string; body: Record<string, unknown> }>,
  };

  const purchaseOrder = () => {
    const paid = state.payments.filter(payment => payment.status === "POSTED").reduce((sum, payment) => sum + Number(payment.amount_origin), 0);
    const received = state.receipts.reduce((sum, receipt) => sum + receipt.received_qty, 0);
    const rejected = state.receipts.reduce((sum, receipt) => sum + receipt.rejected_qty, 0);
    const outstanding = state.status === "CANCELLED" ? 0 : TOTAL - paid;
    return {
      id: 5,
      po_number: "PO-2026-00005",
      order_id: 41,
      order_status: state.orderStatus,
      supplier: { id: 3, name: "Demo Lighting Supplier" },
      status: state.status,
      currency: "USD",
      fx_rate_to_bdt: FX.toFixed(4),
      total_origin: TOTAL.toFixed(2),
      total_bdt: (TOTAL * FX).toFixed(2),
      paid_origin: paid.toFixed(2),
      paid_bdt: (paid * FX).toFixed(2),
      outstanding_origin: outstanding.toFixed(2),
      outstanding_bdt: (outstanding * FX).toFixed(2),
      ordered_qty: ORDERED,
      received_qty: received,
      rejected_qty: rejected,
      expected_at: null,
      note: null,
      created_at: "2026-11-01T04:00:00Z",
      updated_at: "2026-11-01T04:00:00Z",
      allowed_statuses: NEXT_STATUSES[state.status],
      items: [{ id: 1, variant_id: 9, product_name: "LED Desk Lamp", variant_name: "Warm white", qty: ORDERED, unit_cost_origin: "12.50", line_total_origin: TOTAL.toFixed(2) }],
      receipts: state.receipts,
      payments: state.payments,
    };
  };

  const install = async (page: Page) => {
    await page.route("**/api/**", async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const method = request.method();
      const body = method === "POST" ? (request.postDataJSON() as Record<string, unknown>) : {};
      if (method === "POST") state.requests.push({ path, body });

      if (path === "/api/auth/session/") {
        return route.fulfill({ json: { authenticated: true, can_refresh: true, user: { id: 7, username: "erp-admin", role: "admin" } } });
      }
      if (path === "/api/admin/erp/summary/") {
        const open = state.exists && !["CLOSED", "CANCELLED"].includes(state.status);
        const byStatus = { DRAFT: 0, SENT: 0, CONFIRMED: 0, RECEIVED: 0, CLOSED: 0, CANCELLED: 0, ...(state.exists ? { [state.status]: 1 } : {}) };
        return route.fulfill({
          json: {
            orders_awaiting_purchase: state.exists ? 0 : 1,
            purchase_orders: byStatus,
            open_purchase_orders: open ? 1 : 0,
            payables_outstanding_bdt: open ? purchaseOrder().outstanding_bdt : "0.00",
            payables_count: open ? 1 : 0,
            payables_over_60_bdt: "0.00",
          },
        });
      }
      if (path === "/api/admin/purchase-orders/" && method === "GET") {
        const items = state.exists ? [purchaseOrder()] : [];
        return route.fulfill({ json: { items, total: items.length, page: 1, page_size: 25, pages: 1 } });
      }
      if (path === "/api/admin/orders/41/purchase-orders/" && method === "POST") {
        state.exists = true;
        return route.fulfill({ status: 201, json: purchaseOrder() });
      }
      if (path === "/api/admin/purchase-orders/5/" && method === "GET") {
        return route.fulfill({ json: purchaseOrder() });
      }
      if (path === "/api/admin/purchase-orders/5/status/" && method === "POST") {
        state.status = String(body.status);
        if (state.status === "CONFIRMED") state.orderStatus = "PURCHASED";
        return route.fulfill({ json: purchaseOrder() });
      }
      if (path === "/api/admin/purchase-orders/5/receipts/" && method === "POST") {
        state.receipts.push({
          id: state.receipts.length + 1,
          received_qty: Number(body.received_qty),
          accepted_qty: Number(body.accepted_qty),
          rejected_qty: Number(body.rejected_qty),
          qc_note: (body.qc_note as string | undefined) ?? null,
          received_at: "2026-11-05T05:00:00Z",
        });
        if (state.receipts.reduce((sum, receipt) => sum + receipt.received_qty, 0) >= ORDERED) state.status = "RECEIVED";
        return route.fulfill({ status: 201, json: purchaseOrder() });
      }
      if (path === "/api/admin/purchase-orders/5/payments/" && method === "POST") {
        const amount = Number(body.amount_origin);
        state.payments.push({
          id: state.payments.length + 1,
          amount_origin: amount.toFixed(2),
          currency: "USD",
          fx_rate_to_bdt: FX.toFixed(4),
          amount_bdt: (amount * FX).toFixed(2),
          method: String(body.method),
          reference: (body.reference as string | undefined) ?? null,
          paid_at: "2026-11-06T05:00:00Z",
          status: "POSTED",
        });
        return route.fulfill({ status: 201, json: purchaseOrder() });
      }
      if (path === "/api/admin/finance/payables/") {
        return route.fulfill({
          json: {
            generated_at: "2026-11-13T04:00:00Z",
            items: [
              { ...purchaseOrder(), status: "SENT", allowed_statuses: [], age_days: 12, age_bucket: "0_30" },
              { ...purchaseOrder(), id: 6, po_number: "PO-2026-00006", status: "RECEIVED", allowed_statuses: [], outstanding_origin: "80.00", outstanding_bdt: "10000.00", age_days: 75, age_bucket: "over_60" },
            ],
            total_outstanding_bdt: "41250.00",
            aging_bdt: { "0_30": "31250.00", "31_60": "0.00", over_60: "10000.00" },
            note: "Outstanding amounts are converted to BDT at each purchase order's exchange rate.",
          },
        });
      }
      if (path === "/api/admin/finance/order-pnl/") {
        const base = {
          created_at: "2026-11-01T04:00:00Z",
          gross_collected_bdt: "50000.00",
          refunds_bdt: "0.00",
          net_verified_cash_bdt: "50000.00",
          outstanding_bdt: "0.00",
          quoted_shipping_bdt: "6000.00",
          quoted_duty_vat_bdt: "4000.00",
          supplier_paid_bdt: "0.00",
          actual_cost_bdt: null,
          realized_margin_bdt: null,
        };
        return route.fulfill({
          json: {
            items: [
              { ...base, order_id: 41, status: "PURCHASED", revenue_bdt: "50000.00", purchase_orders: ["PO-2026-00005"], supplier_cost_bdt: "31250.00", supplier_cost_basis: "purchase_order", estimated_margin_bdt: "8750.00" },
              { ...base, order_id: 42, status: "CONFIRMED", revenue_bdt: "30000.00", purchase_orders: [], supplier_cost_bdt: "24000.00", supplier_cost_basis: "quote", estimated_margin_bdt: "-4000.00" },
            ],
            total: 2,
            page: 1,
            page_size: 25,
            pages: 1,
          },
        });
      }
      return route.fulfill({ status: 404, json: { detail: "Not found in ERP test" } });
    });
  };

  return { state, install };
}

test.describe("@roles admin ERP modules", () => {
  test("groups the admin menu by business function", async ({ page }) => {
    const backOffice = createBackOffice();
    await backOffice.install(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto("/admin/procurement");

    await expect(page.getByRole("heading", { name: "Supplier purchase orders", exact: true })).toBeVisible();
    for (const moduleName of ["Dashboard", "Sales", "Procurement", "Finance", "Customers", "Master data", "System"]) {
      await expect(page.getByRole("group", { name: moduleName, exact: true })).toBeVisible();
    }
    await expect(page.getByRole("group", { name: "Procurement", exact: true }).getByRole("link", { name: "Purchase orders" })).toBeVisible();
    const finance = page.getByRole("group", { name: "Finance", exact: true });
    await expect(finance.getByRole("link", { name: "Supplier payables" })).toBeVisible();
    await expect(finance.getByRole("link", { name: "Order profit & loss" })).toBeVisible();
  });

  test("takes a purchase order from the customer order to closed", async ({ page }) => {
    const backOffice = createBackOffice();
    await backOffice.install(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto("/admin/procurement");
    const summary = page.getByRole("region", { name: "Procurement summary" });
    await expect(summary.getByText("Orders awaiting a PO")).toBeVisible();
    await expect(page.getByText("No purchase orders yet")).toBeVisible();

    await page.getByLabel("Customer order no.").fill("41");
    await page.getByRole("button", { name: "Raise purchase order" }).click();

    await expect(page).toHaveURL(/\/admin\/procurement\/5$/);
    await expect(page.getByRole("heading", { name: /PO-2026-00005/ })).toContainText("Draft");
    await expect(page.getByText("Demo Lighting Supplier")).toBeVisible();
    await expect(page.getByText("Next step: Send this purchase order to the supplier.")).toBeVisible();
    await expect(page.getByRole("cell", { name: "LED Desk Lamp" })).toBeVisible();
    // Nothing can be received or paid before the supplier has the order.
    await expect(page.getByRole("button", { name: "Record goods received" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Record supplier payment" })).toHaveCount(0);

    const dialog = page.getByRole("dialog");
    const confirm = dialog.getByRole("button", { name: "Confirm" });

    await page.getByRole("button", { name: "Mark sent to supplier" }).click();
    await dialog.getByLabel("Note (required)").fill("Emailed to the supplier");
    await confirm.click();
    await expect(page.getByRole("heading", { name: /PO-2026-00005/ })).toContainText("Sent to supplier");

    await page.getByRole("button", { name: "Mark supplier confirmed" }).click();
    await dialog.getByLabel("Note (required)").fill("Supplier confirmed by email");
    await confirm.click();
    await expect(page.getByRole("heading", { name: /PO-2026-00005/ })).toContainText("Supplier confirmed");
    // Confirming the purchase moves the customer order on.
    await expect(page.getByText("(PURCHASED)")).toBeVisible();

    await page.getByRole("button", { name: "Record goods received" }).click();
    await expect(dialog.getByLabel("Units received (20 still expected)")).toHaveValue("20");
    await dialog.getByLabel("Units rejected at quality check").fill("2");
    await dialog.getByLabel("QC note (required when units are rejected)").fill("Two lamps arrived cracked");
    await confirm.click();
    await expect(page.getByRole("heading", { name: /PO-2026-00005/ })).toContainText("Goods received");
    await expect(page.getByText("20 / 20")).toBeVisible();
    await expect(page.getByText("2 rejected at quality check")).toBeVisible();
    await expect(page.getByRole("cell", { name: "Two lamps arrived cracked" })).toBeVisible();

    await page.getByRole("button", { name: "Record supplier payment" }).click();
    await expect(dialog.getByLabel("Amount (USD), 250.00 outstanding")).toHaveValue("250.00");
    await dialog.getByLabel("Bank or transaction reference").fill("TT-778899");
    await dialog.getByLabel("Note (required)").fill("Full balance by bank transfer");
    await confirm.click();
    await expect(page.getByRole("cell", { name: "TT-778899" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Posted" })).toBeVisible();
    // Fully paid: no further payment can be recorded.
    await expect(page.getByRole("button", { name: "Record supplier payment" })).toHaveCount(0);

    await page.getByRole("button", { name: "Close purchase order" }).click();
    await dialog.getByLabel("Note (required)").fill("Goods received and supplier paid");
    await confirm.click();
    await expect(page.getByRole("heading", { name: /PO-2026-00005/ })).toContainText("Closed");
    await expect(page.getByText("Next step: This purchase order is complete.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Reverse" })).toHaveCount(0);

    expect(backOffice.state.requests).toEqual([
      { path: "/api/admin/orders/41/purchase-orders/", body: {} },
      { path: "/api/admin/purchase-orders/5/status/", body: { status: "SENT", note: "Emailed to the supplier" } },
      { path: "/api/admin/purchase-orders/5/status/", body: { status: "CONFIRMED", note: "Supplier confirmed by email" } },
      { path: "/api/admin/purchase-orders/5/receipts/", body: { received_qty: 20, accepted_qty: 18, rejected_qty: 2, qc_note: "Two lamps arrived cracked" } },
      { path: "/api/admin/purchase-orders/5/payments/", body: { amount_origin: 250, method: "Bank transfer", reference: "TT-778899", note: "Full balance by bank transfer" } },
      { path: "/api/admin/purchase-orders/5/status/", body: { status: "CLOSED", note: "Goods received and supplier paid" } },
    ]);
  });

  test("shows supplier payables by age and order margin with its basis", async ({ page }) => {
    const backOffice = createBackOffice();
    await backOffice.install(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    await page.goto("/admin/finance/payables");
    await expect(page.getByRole("heading", { name: "Supplier payables", exact: true })).toBeVisible();
    const aging = page.getByRole("region", { name: "Payables aging" });
    await expect(aging.getByText("0–30 days")).toBeVisible();
    await expect(aging.getByText("31–60 days")).toBeVisible();
    await expect(aging.getByText("Over 60 days")).toBeVisible();
    await expect(aging.getByText("2 purchase orders")).toBeVisible();
    await expect(page.getByRole("link", { name: "PO-2026-00006" })).toHaveAttribute("href", "/admin/procurement/6");
    await expect(page.getByText("75 days")).toBeVisible();
    await expect(page.getByText("Outstanding amounts are converted to BDT at each purchase order's exchange rate.")).toBeVisible();

    await page.goto("/admin/finance/pnl");
    await expect(page.getByRole("heading", { name: "Order profit and loss", exact: true })).toBeVisible();
    await expect(page.getByText(/Estimated margin = revenue − supplier cost/)).toBeVisible();
    const withPurchaseOrder = page.getByRole("row").filter({ hasText: "#41" });
    await expect(withPurchaseOrder.getByText("PO-2026-00005")).toBeVisible();
    await expect(withPurchaseOrder.locator(".admin-positive")).toHaveCount(1);
    const quoteOnly = page.getByRole("row").filter({ hasText: "#42" });
    await expect(quoteOnly.getByText("from quote, no PO yet")).toBeVisible();
    await expect(quoteOnly.locator(".admin-negative")).toHaveCount(1);
    // Realized margin stays blank until an actual total cost is entered.
    await expect(quoteOnly.getByRole("cell").last()).toHaveText("—");
  });
});
