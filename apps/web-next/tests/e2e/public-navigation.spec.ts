import { expect, test } from "@playwright/test";

test("@public login exposes separate customer and admin portals", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in to SourceAI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Customer" })).toBeVisible();
  await page.getByRole("button", { name: "Admin / operator" }).click();
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open admin dashboard" })).toBeVisible();
});

test("@public primary customer navigation is keyboard reachable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /Source\s*AI/i }).first()).toBeVisible();
  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  await expect(focused).toBeVisible();
});
