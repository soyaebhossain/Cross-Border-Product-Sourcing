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

function scaleOf(transform: string) {
  return Number(/scale\(([\d.]+)\)/.exec(transform)?.[1] ?? "1");
}

test("a product photo zooms in place with the + and - buttons", async ({ page }) => {
  await servePhotos(page, true);
  await page.goto(PRODUCT_WITH_PHOTO);

  const gallery = page.locator(".product-gallery");
  const photo = gallery.locator(".product-gallery__stage .product-image__asset");
  const zoomIn = gallery.getByRole("button", { name: "Zoom in" });
  const zoomOut = gallery.getByRole("button", { name: "Zoom out" });
  const transform = () => photo.evaluate(element => (element as HTMLElement).style.transform);

  await expect(zoomOut).toBeDisabled();
  await zoomIn.click();
  expect(scaleOf(await transform())).toBeCloseTo(1.5, 2);
  await expect(gallery.locator(".product-gallery__hint")).toContainText("150%");
  await zoomIn.click();
  expect(scaleOf(await transform())).toBeCloseTo(2.25, 2);

  // The viewer stays on the product page: no dialog and the same URL.
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(new URL(page.url()).pathname).toBe(PRODUCT_WITH_PHOTO);

  await zoomOut.click();
  await zoomOut.click();
  expect(scaleOf(await transform())).toBe(1);
  await expect(zoomOut).toBeDisabled();

  await gallery.locator(".product-gallery__stage").dblclick({ position: { x: 40, y: 200 } });
  expect(scaleOf(await transform())).toBeCloseTo(2.25, 2);
});

test("a product whose photo cannot load offers no zoom", async ({ page }) => {
  await servePhotos(page, false);
  await page.goto(PRODUCT_WITH_PHOTO);

  await expect(page.locator(".product-gallery .product-image--fallback").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Zoom in" })).toHaveCount(0);
});
