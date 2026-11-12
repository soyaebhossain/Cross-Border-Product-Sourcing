import { expect, test, type Page } from "@playwright/test";

const PRODUCT_WITH_PHOTO = "/products/laptop-pc-accessories-1080p-usb-webcam";
const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function servePhotos(page: Page, available: boolean) {
  for (const pattern of ["**/media/**", "**/_next/image**"]) {
    await page.route(pattern, route =>
      available ? route.fulfill({ status: 200, contentType: "image/png", body: PIXEL }) : route.fulfill({ status: 404, body: "" }),
    );
  }
}

test("a product photo opens in a viewer that zooms, resets and closes", async ({ page }) => {
  await servePhotos(page, true);
  await page.goto(PRODUCT_WITH_PHOTO);

  await page.getByRole("button", { name: /^Zoom .* image$/ }).click();
  const viewer = page.getByRole("dialog");
  await expect(viewer).toBeVisible();
  const level = viewer.locator("output");
  await expect(level).toHaveText("100%");

  await viewer.getByRole("button", { name: "Zoom in" }).click();
  await expect(level).toHaveText("140%");
  await page.keyboard.press("+");
  await expect(level).toHaveText("196%");
  await viewer.getByRole("button", { name: "Reset" }).click();
  await expect(level).toHaveText("100%");
  await expect(viewer.getByRole("button", { name: "Zoom out" })).toBeDisabled();

  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
});

test("a product whose photo cannot load offers no zoom", async ({ page }) => {
  await servePhotos(page, false);
  await page.goto(PRODUCT_WITH_PHOTO);

  await expect(page.locator(".product-gallery .product-image--fallback").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /^Zoom .* image$/ })).toHaveCount(0);
});
