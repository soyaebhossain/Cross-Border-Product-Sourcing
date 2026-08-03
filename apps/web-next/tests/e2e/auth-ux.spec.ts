import { expect, test, type Page } from "@playwright/test";

const unavailableBody = JSON.stringify({ detail: "Auth service intentionally unavailable in public E2E" });

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", route =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: unavailableBody,
    }),
  );
});

async function mockReadiness(page: Page, ready: boolean) {
  await page.route("**/api/ready", route =>
    route.fulfill({
      status: ready ? 200 : 404,
      contentType: "application/json",
      body: JSON.stringify(ready ? { status: "ready" } : { detail: "Not Found" }),
    }),
  );
}

async function expectMobileAuthPageFits(page: Page, path: "/login" | "/signup") {
  await page.goto(path);
  await expect(page.locator(".auth-service-status")).toContainText("Account service offline");

  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();

  const measurements = await page.evaluate(() => {
    const card = document.querySelector<HTMLElement>(".auth-card");
    const intro = card?.querySelector<HTMLElement>(":scope > div");
    const form = card?.querySelector<HTMLElement>(":scope > form");
    if (!card || !intro || !form) return null;
    const cardBox = card.getBoundingClientRect();
    const introBox = intro.getBoundingClientRect();
    const formBox = form.getBoundingClientRect();
    const controls = Array.from(
      card.querySelectorAll<HTMLElement>("input, button, a"),
    )
      .filter(element => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      })
      .map(element => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right };
      });
    return {
      viewportWidth: window.innerWidth,
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      card: { left: cardBox.left, right: cardBox.right },
      introBottom: introBox.bottom,
      formTop: formBox.top,
      controls,
    };
  });

  expect(measurements).not.toBeNull();
  expect(measurements!.overflow).toBeLessThanOrEqual(1);
  expect(measurements!.card.left).toBeGreaterThanOrEqual(-0.5);
  expect(measurements!.card.right).toBeLessThanOrEqual(measurements!.viewportWidth + 0.5);
  expect(measurements!.formTop).toBeGreaterThanOrEqual(measurements!.introBottom - 1);
  expect(measurements!.controls.length).toBeGreaterThan(0);
  expect(
    measurements!.controls.every(
      control => control.left >= -0.5 && control.right <= measurements!.viewportWidth + 0.5,
    ),
  ).toBe(true);
}

test("@public offline login reports service availability without blaming credentials", async ({ page }) => {
  let releaseInitialCheck!: () => void;
  const initialCheckGate = new Promise<void>(resolve => {
    releaseInitialCheck = resolve;
  });
  let readinessChecks = 0;
  let loginRequests = 0;

  await page.route("**/api/ready", async route => {
    readinessChecks += 1;
    if (readinessChecks === 1) await initialCheckGate;
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Not Found" }),
    });
  });
  await page.route("**/api/auth/login/", route => {
    loginRequests += 1;
    return route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid credentials" }),
    });
  });

  await page.goto("/login");
  const google = page.getByRole("button", { name: "Continue with Google" });
  const submit = page.getByRole("button", { name: "Sign in securely" });
  await expect(page.locator(".auth-service-status")).toContainText("Checking secure connection");
  await expect(google).toBeDisabled();
  await expect(submit).toBeDisabled();

  releaseInitialCheck();
  const serviceStatus = page.locator(".auth-service-status");
  await expect(serviceStatus).toContainText("Account service offline");
  const retry = serviceStatus.getByRole("button", { name: "Retry" });
  await expect(retry).toBeVisible();
  await expect(google).toBeDisabled();

  await page.getByLabel("Username, email or phone").fill("offline-customer");
  await page.getByLabel("Password", { exact: true }).fill("A9!Offline-Credential");
  await expect(submit).toBeEnabled();

  await retry.click();
  await expect.poll(() => readinessChecks).toBeGreaterThanOrEqual(2);
  await expect(serviceStatus).toContainText("Account service offline");

  await submit.click();
  const alert = page.locator(".form-error[role='alert']");
  await expect(alert).toContainText("The account service is not connected");
  await expect(alert).toContainText("Your credentials were not rejected");
  await expect(alert).not.toContainText(/invalid credentials|password is incorrect/i);
  await expect.poll(() => readinessChecks).toBeGreaterThanOrEqual(3);
  expect(loginRequests).toBe(0);
});

test("@public customer and admin portal selection stays synchronized with the URL", async ({ page }) => {
  await mockReadiness(page, true);
  await page.goto("/login");
  await expect(page.locator(".auth-service-status")).toContainText("Account service online");

  const customer = page.getByRole("button", { name: "Customer", exact: true });
  const admin = page.getByRole("button", { name: "Admin / operator" });
  await expect(page.getByRole("group", { name: "Choose login type" })).toBeVisible();
  await expect(customer).toHaveAttribute("aria-pressed", "true");
  await expect(admin).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("heading", { name: "Sign in to SourceAI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();

  await admin.click();
  await expect(page).toHaveURL(url => url.pathname === "/login" && url.searchParams.get("portal") === "admin");
  await expect(admin).toHaveAttribute("aria-pressed", "true");
  await expect(customer).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open admin dashboard" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toHaveCount(0);

  await page.reload();
  await expect(page.locator(".auth-service-status")).toContainText("Account service online");
  await expect(admin).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();

  await customer.click();
  await expect(page).toHaveURL(url => url.pathname === "/login" && !url.searchParams.has("portal"));
  await expect(customer).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Sign in to SourceAI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
});

test("@public login fields expose decorative icons and an accessible password reveal", async ({ page }) => {
  await mockReadiness(page, true);
  await page.goto("/login");
  await expect(page.locator(".auth-service-status")).toContainText("Account service online");

  const fieldIcons = page.locator("form .auth-field > span svg");
  await expect(fieldIcons).toHaveCount(2);
  for (let index = 0; index < 2; index += 1) {
    await expect(fieldIcons.nth(index)).toHaveAttribute("aria-hidden", "true");
    await expect(fieldIcons.nth(index)).toHaveAttribute("focusable", "false");
  }

  const password = page.getByLabel("Password", { exact: true });
  const reveal = page.getByRole("button", { name: "Show password" });
  await expect(password).toHaveAttribute("type", "password");
  await expect(reveal).toHaveAttribute("aria-pressed", "false");

  await reveal.click();
  await expect(password).toHaveAttribute("type", "text");
  const hide = page.getByRole("button", { name: "Hide password" });
  await expect(hide).toHaveAttribute("aria-pressed", "true");

  await hide.click();
  await expect(password).toHaveAttribute("type", "password");
  await expect(page.getByRole("button", { name: "Show password" })).toHaveAttribute("aria-pressed", "false");
});

test("@public signup exposes confirmation mismatch before registration", async ({ page }) => {
  await mockReadiness(page, true);
  await page.goto("/signup");
  await expect(page.locator(".auth-service-status")).toContainText("Account service online");

  const fieldIcons = page.locator("form .auth-field > span svg");
  await expect(fieldIcons).toHaveCount(5);

  await page.getByLabel("Username", { exact: true }).fill("new-customer");
  await page.getByLabel("Email", { exact: true }).fill("new-customer@example.test");
  const password = page.getByLabel("Password", { exact: true });
  const confirmation = page.getByLabel("Confirm password", { exact: true });
  const strongPassword = "A9!Violet-Cedar";
  await password.fill(strongPassword);
  await confirmation.fill(`${strongPassword}-different`);

  await expect(page.locator(".password-policy .password-policy--met")).toHaveCount(5);
  await expect(confirmation).toHaveAttribute("aria-invalid", "true");
  await expect(confirmation.locator("..")).toHaveClass(/auth-input--invalid/);
  const submit = page.getByRole("button", { name: "Create secure account" });
  await expect(submit).toBeDisabled();

  const reveal = page.getByRole("button", { name: "Show password" });
  await expect(reveal).toHaveAttribute("aria-pressed", "false");
  await reveal.click();
  await expect(password).toHaveAttribute("type", "text");
  await expect(page.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
  await expect(confirmation).toHaveAttribute("type", "text");

  await confirmation.fill(strongPassword);
  await expect(confirmation).toHaveAttribute("aria-invalid", "false");
  await expect(confirmation.locator("..")).not.toHaveClass(/auth-input--invalid/);
  await expect(submit).toBeEnabled();
});

test("@public MFA method selector exposes its selected state", async ({ page }) => {
  await mockReadiness(page, true);
  await page.route("**/api/auth/login/", route =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        mfa_required: true,
        mfa_enrollment_required: false,
        mfa_token: "audit-mfa-token",
        expires_in: 300,
      }),
    }),
  );

  await page.goto("/login?portal=admin");
  await expect(page.locator(".auth-service-status")).toContainText("Account service online");
  await page.getByLabel("Username, email or phone").fill("audit-admin");
  await page.getByLabel("Password", { exact: true }).fill("A9!Audit-Credential");
  await page.getByRole("button", { name: "Open admin dashboard" }).click();

  const group = page.getByRole("group", { name: "Verification method" });
  const authenticator = group.getByRole("button", { name: "Authenticator code" });
  const recovery = group.getByRole("button", { name: "Recovery code" });
  await expect(authenticator).toHaveAttribute("aria-pressed", "true");
  await expect(recovery).toHaveAttribute("aria-pressed", "false");

  await recovery.click();
  await expect(authenticator).toHaveAttribute("aria-pressed", "false");
  await expect(recovery).toHaveAttribute("aria-pressed", "true");
});

test("@public mobile admin drawer restores focus to its trigger", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Mobile drawer focus contract");
  await page.route("**/api/auth/me/", route =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        username: "audit-admin",
        email: "audit-admin@example.test",
        role: "admin",
      }),
    }),
  );

  await page.goto("/admin");
  const trigger = page.getByRole("button", { name: "Admin menu" });
  const triggerElement = page.locator(".admin-sidebar-toggle");
  await trigger.click();
  const drawer = page.getByRole("dialog", { name: "Admin navigation" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("button", { name: "Close admin menu" })).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await expect(trigger).toBeFocused();

  await trigger.click();
  await expect(drawer).toBeVisible();
  await page.setViewportSize({ width: 1000, height: 900 });
  await expect(triggerElement).toBeHidden();
  await expect(triggerElement).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#admin-navigation [aria-current='page']")).toBeFocused();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
});

test("@public auth cards stack and remain within the mobile viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Mobile layout contract");
  await mockReadiness(page, false);
  await expectMobileAuthPageFits(page, "/login");
  await expectMobileAuthPageFits(page, "/signup");
});
