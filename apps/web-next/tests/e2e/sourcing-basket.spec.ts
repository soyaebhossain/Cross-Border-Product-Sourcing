import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.removeItem("sourceai-sourcing-basket-v1"));
});

test("@public product cards support a persistent sourcing basket", async ({ page }) => {
  await page.goto("/products?q=1080p%20USB%20Webcam");
  const card = page.getByRole("article").filter({ hasText: "1080p USB Webcam" });
  await expect(card).toBeVisible();
  await expect(card.getByText(/From.*\$16\.20/)).toBeVisible();
  await expect(card.getByText("Excludes shipping, tariff, VAT, and customs charges.")).toBeVisible();

  await card.getByRole("button", { name: "Add to quote" }).click();
  const toast = page.getByRole("status").filter({ hasText: "Added to sourcing basket" });
  await expect(toast).toBeVisible();
  await expect(page.locator('[aria-label="Sourcing basket: 1"]:visible')).toHaveCount(1);

  await expect(toast.getByRole("link", { name: "View basket" })).toHaveAttribute("href", "/sourcing-basket");
  await page.goto("/sourcing-basket");
  await expect(page).toHaveURL(/\/sourcing-basket$/);
  await expect(page.getByRole("heading", { name: "Sourcing basket" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "1080p USB Webcam" })).toBeVisible();

  const quantity = page.getByRole("spinbutton", { name: "Quantity: 1080p USB Webcam" });
  await expect(quantity).toHaveValue("1");
  await page.getByRole("button", { name: "Quantity: 1080p USB Webcam: increase" }).click();
  await expect(quantity).toHaveValue("2");

  await page.getByRole("button", { name: "Remove: 1080p USB Webcam" }).click();
  await expect(page.getByRole("heading", { name: "Your sourcing basket is empty" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue sourcing" })).toBeVisible();
});

test("@public product detail exposes the sourcing action panel", async ({ page }) => {
  await page.goto("/products/laptop-pc-accessories-1080p-usb-webcam");
  const panel = page.getByRole("complementary", { name: "Build your sourcing request" });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("combobox", { name: "Variant" })).toBeVisible();
  await expect(panel.getByRole("combobox", { name: "Origin" })).toBeVisible();
  await panel.getByRole("button", { name: "Add to quote" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Added to sourcing basket" })).toBeVisible();
});

test("basket preview product row opens product details", async ({ page }) => {
  await page.goto("/products?q=1080p%20USB%20Webcam");
  const card = page.getByRole("article").filter({ hasText: "1080p USB Webcam" });
  await card.getByRole("button", { name: "Add to quote" }).click();

  await page.getByRole("button", { name: "Sourcing basket: 1" }).click();
  const preview = page.getByRole("dialog", { name: "Sourcing basket" });
  const productLink = preview.getByRole("link", { name: "View product: 1080p USB Webcam" });
  await expect(productLink).toHaveAttribute("href", "/products/laptop-pc-accessories-1080p-usb-webcam");
  await productLink.click();

  await expect(page).toHaveURL(/\/products\/laptop-pc-accessories-1080p-usb-webcam$/);
  await expect(page.getByRole("heading", { name: "1080p USB Webcam", level: 1 })).toBeVisible();
});

test("basket language follows the saved locale", async ({ page }) => {
  await page.goto("/products?q=1080p%20USB%20Webcam");
  const card = page.getByRole("article").filter({ hasText: "1080p USB Webcam" });
  await card.getByRole("button", { name: "Add to quote" }).click();

  await page.getByRole("button", { name: "Switch to Bangla" }).click();
  await page.getByRole("button", { name: "সোর্সিং বাস্কেট: 1" }).click();
  const banglaPreview = page.getByRole("dialog", { name: "সোর্সিং বাস্কেট" });
  await expect(banglaPreview.getByText("আনুমানিক পণ্য মূল্য")).toBeVisible();
  await expect(banglaPreview.getByRole("link", { name: "বাস্কেট দেখুন" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: "ইংরেজি ভাষা বেছে নিন" })).toBeVisible();
  await page.getByRole("button", { name: "ইংরেজি ভাষা বেছে নিন" }).click();
  await page.getByRole("button", { name: "Sourcing basket: 1" }).click();
  const englishPreview = page.getByRole("dialog", { name: "Sourcing basket" });
  await expect(englishPreview.getByText("Estimated product cost")).toBeVisible();
  await expect(englishPreview.getByRole("link", { name: "View basket" })).toBeVisible();
});
