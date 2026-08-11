import { expect, test, type Page } from "@playwright/test";
import type { CustomerProfile } from "../../lib/customer-api";

const baseProfile: CustomerProfile = {
  user_id: 123,
  username: "123@456",
  email: "customer@example.test",
  phone: "+8801700000000",
  full_name: "Soyaeb Hossain",
  company: {
    name: "SourceAI Trading",
    registration_number: "RJSC-2026-1042",
    tax_identifier: "TIN-849201",
  },
  preferences: {
    language: "en" as const,
    currency: "BDT",
    timezone: "Asia/Dhaka",
  },
};

const addressFixtures = [
  {
    id: 1,
    label: "Head office",
    recipient_name: "Soyaeb Hossain",
    company_name: "SourceAI Trading",
    line1: "House 14, Road 8",
    line2: "Banani",
    city: "Dhaka",
    region: "Dhaka",
    postal_code: "1213",
    country_code: "BD",
    phone: "+8801700000000",
    is_default_shipping: true,
    is_default_billing: true,
  },
  {
    id: 2,
    label: "Warehouse",
    recipient_name: "Operations Team",
    company_name: "SourceAI Trading",
    line1: "Plot 22, Logistics Avenue",
    line2: null,
    city: "Narayanganj",
    region: "Dhaka",
    postal_code: "1400",
    country_code: "BD",
    phone: "+8801800000000",
    is_default_shipping: false,
    is_default_billing: false,
  },
];

async function mockProfileApi(page: Page, addresses = addressFixtures) {
  let profile: CustomerProfile = structuredClone(baseProfile);
  let savedPayload: Record<string, unknown> | null = null;

  await page.route("**/api/auth/me/", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      id: 123,
      username: baseProfile.username,
      email: baseProfile.email,
      role: "customer",
    }),
  }));

  await page.route("**/api/account/profile/", async route => {
    if (route.request().method() === "PATCH") {
      savedPayload = route.request().postDataJSON() as Record<string, unknown>;
      profile = {
        ...profile,
        full_name: (savedPayload.full_name as string | null) || null,
        company: {
          name: (savedPayload.company_name as string | null) || null,
          registration_number: (savedPayload.company_registration_number as string | null) || null,
          tax_identifier: (savedPayload.tax_identifier as string | null) || null,
        },
        preferences: {
          language: savedPayload.preferred_language as "en" | "bn",
          currency: savedPayload.preferred_currency as string,
          timezone: savedPayload.timezone as string,
        },
      };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(profile),
    });
  });

  await page.route("**/api/account/addresses/", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(addresses),
  }));

  return { getSavedPayload: () => savedPayload };
}

function spread(values: number[]) {
  return Math.max(...values) - Math.min(...values);
}

test("@public customer profile uses a consistent professional form layout", async ({ page }) => {
  await mockProfileApi(page, []);
  await page.goto("/account/profile");

  await expect(page.getByRole("heading", { name: "Profile and addresses", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Person and company", level: 2 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Address book", level: 2 })).toBeVisible();
  await expect(page.getByText("No saved addresses yet")).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);

  const panels = page.locator(".account-panel");
  await expect(panels).toHaveCount(2);
  const panelRects = await panels.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect()));
  expect(spread(panelRects.map(rect => rect.x))).toBeLessThanOrEqual(1);
  expect(spread(panelRects.map(rect => rect.width))).toBeLessThanOrEqual(1);

  const form = page.locator(".account-profile-form");
  const fields = form.locator("label");
  const controls = form.locator("input, select");
  await expect(fields).toHaveCount(7);
  await expect(controls).toHaveCount(7);

  const fieldMetrics = await fields.evaluateAll(nodes => nodes.map(node => {
    const field = node.getBoundingClientRect();
    const label = node.querySelector(":scope > span")!.getBoundingClientRect();
    const control = node.querySelector("input, select")!.getBoundingClientRect();
    return {
      x: field.x,
      y: field.y,
      width: field.width,
      height: field.height,
      controlX: control.x,
      controlY: control.y,
      controlWidth: control.width,
      controlHeight: control.height,
      labelBottom: label.bottom,
    };
  }));

  expect(Math.min(...fieldMetrics.map(metric => metric.controlHeight))).toBeGreaterThanOrEqual(44);
  expect(spread(fieldMetrics.map(metric => metric.controlHeight))).toBeLessThanOrEqual(1);
  expect(Math.max(...fieldMetrics.map(metric => Math.abs(metric.width - metric.controlWidth)))).toBeLessThanOrEqual(1);
  expect(Math.max(...fieldMetrics.map(metric => Math.abs(metric.x - metric.controlX)))).toBeLessThanOrEqual(1);
  expect(Math.min(...fieldMetrics.map(metric => metric.controlY - metric.labelBottom))).toBeGreaterThanOrEqual(6);

  const viewportWidth = page.viewportSize()!.width;
  if (viewportWidth > 760) {
    const sectionRows = await form.locator("section").evaluateAll(sections => sections.map(section => (
      [...section.querySelectorAll("label")].map(label => label.getBoundingClientRect())
    )));
    for (const row of sectionRows) {
      expect(spread(row.map(rect => rect.y))).toBeLessThanOrEqual(1);
      expect(spread(row.map(rect => rect.width))).toBeLessThanOrEqual(2);
    }
    await expect(page.locator(".account-sidebar")).toBeVisible();
    await expect(page.locator(".account-mobile-nav")).toBeHidden();
    await expect(page.getByRole("link", { name: "Profile & addresses" })).toHaveAttribute("aria-current", "page");
  } else {
    expect(spread(fieldMetrics.map(metric => metric.x))).toBeLessThanOrEqual(1);
    expect(spread(fieldMetrics.map(metric => metric.width))).toBeLessThanOrEqual(1);
    await expect(page.locator(".account-sidebar")).toBeHidden();
    await expect(page.locator(".account-mobile-nav")).toBeVisible();
    await expect(page.locator(".account-mobile-nav select")).toHaveValue("/account/profile");
  }

  const ids = await page.locator("[id]").evaluateAll(nodes => nodes.map(node => node.id));
  expect(new Set(ids).size).toBe(ids.length);

  const addAddress = page.getByRole("button", { name: "Add address", exact: true });
  const addButtonBox = await addAddress.boundingBox();
  expect(addButtonBox!.height).toBeGreaterThanOrEqual(44);
  await addAddress.click();
  const dialog = page.getByRole("dialog", { name: "Add address" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Recipient name")).toBeVisible();
  await expect(dialog.getByLabel("Phone")).toHaveAttribute("type", "tel");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(addAddress).toBeFocused();
});

test("@public profile saving and address cards remain usable", async ({ page }) => {
  const api = await mockProfileApi(page);
  await page.goto("/account/profile");

  const cards = page.locator(".account-address-card");
  await expect(cards).toHaveCount(2);
  const cardRects = await cards.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect()));
  expect(spread(cardRects.map(rect => rect.width))).toBeLessThanOrEqual(1);
  expect(spread(cardRects.map(rect => rect.height))).toBeLessThanOrEqual(1);
  expect(Math.max(...cardRects.map(rect => rect.right))).toBeLessThanOrEqual(page.viewportSize()!.width + 1);

  await expect(page.getByRole("button", { name: "Edit Head office address" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove Head office address" })).toBeVisible();
  await page.getByRole("button", { name: "Edit Head office address" }).click();
  const editDialog = page.getByRole("dialog", { name: "Edit address" });
  await expect(editDialog.getByLabel("Address line 1")).toHaveValue("House 14, Road 8");
  await page.keyboard.press("Escape");

  await page.getByLabel(/^Full name/).fill("Soyaeb Hossain Updated");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("status")).toContainText("Profile saved.");
  expect(api.getSavedPayload()).toMatchObject({ full_name: "Soyaeb Hossain Updated" });
});

test("@public address dialogs remain open while saving and surface deletion errors", async ({ page }) => {
  await mockProfileApi(page);
  await page.route("**/api/account/addresses/", async route => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 750));
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ ...addressFixtures[0], id: 3, label: "New office" }),
    });
  });
  await page.route("**/api/account/addresses/1/", route => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ detail: "Address service is temporarily unavailable." }),
  }));
  await page.goto("/account/profile");

  await page.getByRole("button", { name: "Add address", exact: true }).click();
  const addDialog = page.getByRole("dialog", { name: "Add address" });
  await addDialog.getByLabel("Label").fill("New office");
  await addDialog.getByLabel("Recipient name").fill("Operations Team");
  await addDialog.getByLabel("Address line 1").fill("12 Test Road");
  await addDialog.getByLabel("City").fill("Dhaka");
  await addDialog.getByLabel("Phone").fill("+8801700000000");
  await addDialog.getByRole("button", { name: "Save" }).click();
  await expect(addDialog.getByRole("button", { name: "Saving…" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(addDialog).toBeVisible();
  await expect(addDialog).toBeHidden();

  await page.getByRole("button", { name: "Remove Head office address" }).click();
  const removeDialog = page.getByRole("dialog", { name: "Remove address?" });
  await removeDialog.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(removeDialog).toBeVisible();
  await expect(removeDialog.getByRole("alert")).toHaveText("Address service is temporarily unavailable.");
  await expect(page.locator(".account-page > .account-alert")).toHaveCount(0);
});
