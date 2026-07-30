import { expect, test } from "@playwright/test";

const products = [
  {
    id: 1,
    name: "USB-C Wall Charger",
    slug: "usb-c-wall-charger",
    model: "SC-01",
    image: "/media/products/OIP.webp",
    category: { id: 1, name: "Mobile Accessories", slug: "mobile-accessories" },
    variant_count: 1,
    offer_count: 4,
    is_active: true,
  },
  {
    id: 2,
    name: "Aluminium Laptop Stand",
    slug: "aluminium-laptop-stand",
    model: "LS-01",
    image: null,
    category: { id: 2, name: "Laptop & PC Accessories", slug: "laptop-pc-accessories" },
    variant_count: 1,
    offer_count: 4,
    is_active: true,
  },
];

test.describe("@roles admin product media", () => {
  test("shows completeness, filters missing images and saves an audited image URL", async ({ page }) => {
    let submittedBody: Record<string, unknown> | null = null;
    await page.route("**/api/**", async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path === "/api/auth/me/") {
        await route.fulfill({ json: { id: 7, username: "catalog-admin", role: "admin" } });
        return;
      }
      if (path === "/api/admin/products/" && request.method() === "GET") {
        await route.fulfill({
          json: { items: products, total: products.length, page: 1, page_size: 100, pages: 1 },
        });
        return;
      }
      if (path === "/api/admin/products/2/" && request.method() === "PATCH") {
        submittedBody = request.postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          json: {
            ...products[1],
            image: submittedBody.image,
            description: null,
            archived_at: null,
            category: { ...products[1].category, product_count: 1, is_active: true },
            variants: [],
          },
        });
        return;
      }
      await route.fulfill({ status: 404, json: { detail: "Not found in media test" } });
    });

    await page.goto("/admin/catalog/media");

    await expect(page.getByRole("heading", { name: "Product media", exact: true })).toBeVisible();
    await expect(page.getByLabel("Image coverage").getByText("Needs image", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Aluminium Laptop Stand" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "USB-C Wall Charger" })).toHaveCount(0);

    await page.getByLabel("Media status").selectOption("all");
    await expect(page.getByRole("heading", { name: "USB-C Wall Charger" })).toBeVisible();
    await page.getByRole("button", { name: "Add image" }).click();

    await expect(page.getByRole("heading", { name: "Add product image" })).toBeVisible();
    await page.getByLabel("HTTPS image URL or public path").fill("/api/private.png");
    await expect(page.getByText("Local product images must use a safe /media/products/ path and a supported image extension.")).toBeVisible();
    await page.getByLabel("HTTPS image URL or public path").fill("https://loremflickr.com/640/480/laptop");
    await expect(page.getByText("Random placeholder services are unreliable. Use an owned, licensed or supplier-approved image.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save image" })).toBeDisabled();
    await page.getByLabel("HTTPS image URL or public path").fill("https://cdn.example.com/laptop-stand.webp");
    await page.getByLabel("Mandatory audit note").fill("Supplier-approved primary catalog photo");
    await page.getByRole("button", { name: "Save image" }).click();

    await expect(page.getByRole("status")).toHaveText("Product image saved with an audit record.");
    expect(submittedBody).toEqual({
      image: "https://cdn.example.com/laptop-stand.webp",
      note: "Supplier-approved primary catalog photo",
    });
    await expect(page.getByText("100%", { exact: true })).toBeVisible();
  });
});
