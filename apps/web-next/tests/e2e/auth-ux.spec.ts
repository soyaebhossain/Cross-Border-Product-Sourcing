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
      body: JSON.stringify(ready
        ? { status: "ready", password_reset_email_configured: true }
        : { detail: "Not Found", password_reset_email_configured: false }),
    }),
  );
}

async function expectMobileAuthPageFits(page: Page, path: "/login" | "/signup" | "/forgot-password") {
  await page.goto(path);
  await expect(page.locator(".auth-service-status")).toContainText(
    /Sign-in service unavailable|Account service offline/,
  );

  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();

  const measurements = await page.evaluate(() => {
    const card = document.querySelector<HTMLElement>(".auth-card");
    const intro = card?.querySelector<HTMLElement>(":scope > :not(form)");
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

const enrollmentSecret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";
const enrollmentUri = `otpauth://totp/SourceAI:e2e-admin?secret=${enrollmentSecret}&issuer=SourceAI&algorithm=SHA1&digits=6&period=30`;

async function openMfaEnrollment(
  page: Page,
  options: { token?: string; secret?: string; uri?: string; expiresIn?: number } = {},
) {
  const token = options.token || "e2e-enrollment-token";
  const secret = options.secret || enrollmentSecret;
  const uri = options.uri || enrollmentUri;
  const expiresIn = options.expiresIn ?? 300;

  await mockReadiness(page, true);
  await page.route("**/api/auth/login/", route =>
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        mfa_required: true,
        mfa_enrollment_required: true,
        mfa_token: token,
        expires_in: expiresIn,
      }),
    }),
  );
  await page.route("**/api/auth/mfa/enroll/start/", route =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ secret, otpauth_uri: uri, message: "Scan or enter the setup key." }),
    }),
  );

  await page.goto("/login?portal=admin");
  await expect(page.locator(".auth-service-status")).toHaveCount(0);
  await page.getByLabel("Username, email or phone").fill("e2e-admin");
  await page.getByLabel("Password", { exact: true }).fill("A9!Enrollment-Credential");
  await page.getByRole("button", { name: "Open admin dashboard" }).click();
  await expect(page.getByRole("heading", { name: "Connect an authenticator app" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Scan QR code with your authenticator app" })).toBeVisible();
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
  await expect(serviceStatus).toContainText("Sign-in service unavailable");
  const retry = serviceStatus.getByRole("button", { name: "Retry" });
  await expect(retry).toBeVisible();
  await expect(google).toBeDisabled();

  await page.getByLabel("Username, email or phone").fill("offline-customer");
  await page.getByLabel("Password", { exact: true }).fill("A9!Offline-Credential");
  await expect(submit).toBeEnabled();

  await retry.click();
  await expect.poll(() => readinessChecks).toBeGreaterThanOrEqual(2);
  await expect(serviceStatus).toContainText("Sign-in service unavailable");

  await submit.click();
  const alert = page.locator(".form-error[role='alert']");
  await expect(alert).toContainText("The account service is not connected");
  await expect(alert).toContainText("Your credentials were not rejected");
  await expect(alert).not.toContainText(/invalid credentials|password is incorrect/i);
  await expect.poll(() => readinessChecks).toBeGreaterThanOrEqual(3);
  expect(loginRequests).toBe(0);
});

test("@public customer and admin portal links stay synchronized with the URL", async ({ page }) => {
  await mockReadiness(page, true);
  await page.goto("/login");
  await expect(page.locator(".auth-service-status")).toHaveCount(0);

  const card = page.locator(".auth-card--login");
  const adminAccess = page.getByRole("link", { name: "Admin / operator access" });
  await expect(card).toHaveAttribute("aria-labelledby", "login-title");
  await expect(card.locator("aside.auth-login-brand")).toHaveCount(1);
  await expect(card.locator('form[name="customer-login"]')).toHaveCount(1);
  await expect(page.getByRole("group", { name: "Choose login type" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Sign in to SourceAI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  await expect(adminAccess).toHaveAttribute("href", "/login?portal=admin");

  await adminAccess.click();
  await expect(page).toHaveURL(url => url.pathname === "/login" && url.searchParams.get("portal") === "admin");
  await expect(page.locator(".auth-service-status")).toHaveCount(0);
  await expect(card.locator('form[name="admin-login"]')).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open admin dashboard" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toHaveCount(0);
  const customerAccess = page.getByRole("link", { name: "Back to customer sign in" });
  await expect(customerAccess).toHaveAttribute("href", "/login");

  await page.reload();
  await expect(page.locator(".auth-service-status")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();

  await page.getByRole("link", { name: "Back to customer sign in" }).click();
  await expect(page).toHaveURL(url => url.pathname === "/login" && !url.searchParams.has("portal"));
  await expect(page.getByRole("heading", { name: "Sign in to SourceAI" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
});

test("@public login fields expose decorative icons and an accessible password reveal", async ({ page }) => {
  await mockReadiness(page, true);
  await page.goto("/login");
  await expect(page.locator(".auth-service-status")).toHaveCount(0);

  const form = page.locator('form[name="customer-login"]');
  const identifier = page.getByLabel("Username, email or phone");
  const fieldIcons = page.locator("form .auth-field > span svg");
  await expect(fieldIcons).toHaveCount(2);
  for (let index = 0; index < 2; index += 1) {
    await expect(fieldIcons.nth(index)).toHaveAttribute("aria-hidden", "true");
    await expect(fieldIcons.nth(index)).toHaveAttribute("focusable", "false");
  }

  const password = page.getByLabel("Password", { exact: true });
  const reveal = page.getByRole("button", { name: "Show password" });
  await expect(form).toHaveAttribute("autocomplete", "on");
  await expect(identifier).toHaveAttribute("name", "username");
  await expect(identifier).toHaveAttribute("autocomplete", "username");
  await expect(password).toHaveAttribute("name", "password");
  await expect(password).toHaveAttribute("autocomplete", "current-password");
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

test("@public remember-me restores only the successful portal identifier and never stores the password", async ({ page }) => {
  await mockReadiness(page, true);
  const loginPayloads: Array<Record<string, unknown>> = [];
  await page.route("**/api/auth/login/", async route => {
    loginPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        mfa_required: true,
        mfa_enrollment_required: false,
        mfa_token: "e2e-mfa-challenge",
        expires_in: 300,
      }),
    });
  });

  const customerId = "remembered.customer@example.com";
  const passwordValue = "A9!Remember-Only-In-Browser";
  await page.goto("/login");
  await expect(page.locator(".auth-service-status")).toHaveCount(0);
  const remember = page.getByRole("checkbox", { name: /Keep me signed in.*Remember my ID/ });
  await expect(remember).toBeChecked();
  await page.getByLabel("Username, email or phone").fill(customerId);
  await page.getByLabel("Password", { exact: true }).fill(passwordValue);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page.getByRole("heading", { name: "Enter your security code" })).toBeVisible();

  expect(loginPayloads).toHaveLength(1);
  expect(loginPayloads[0]).toMatchObject({ identifier: customerId, remember: true, portal: "customer" });
  const firstStorage = await page.evaluate(() => window.localStorage.getItem("sourceai-remembered-login-v1"));
  expect(firstStorage).toContain(customerId);
  expect(firstStorage).not.toContain(passwordValue);

  await page.goto("/login");
  await expect(page.locator(".auth-service-status")).toHaveCount(0);
  await expect(page.getByLabel("Username, email or phone")).toHaveValue(customerId);
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");

  await page.getByRole("link", { name: "Admin / operator access" }).click();
  await expect(page.getByLabel("Username, email or phone")).toHaveValue("");
  await page.getByRole("link", { name: "Back to customer sign in" }).click();
  await expect(page.getByLabel("Username, email or phone")).toHaveValue(customerId);

  await remember.uncheck();
  await page.getByLabel("Password", { exact: true }).fill(passwordValue);
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page.getByRole("heading", { name: "Enter your security code" })).toBeVisible();
  expect(loginPayloads).toHaveLength(2);
  expect(loginPayloads[1]).toMatchObject({ identifier: customerId, remember: false, portal: "customer" });
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("sourceai-remembered-login-v1"))).toBeNull();

  await page.goto("/login");
  await expect(page.getByLabel("Username, email or phone")).toHaveValue("");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
});

test("@public forgot-password is available to both portals and returns a neutral success", async ({ page }) => {
  await mockReadiness(page, true);
  const resetRequests: Array<Record<string, unknown>> = [];
  await page.route("**/api/auth/password-reset/request/", async route => {
    resetRequests.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        message: "If an eligible account matches, a reset link has been sent. Check your spam folder too.",
      }),
    });
  });

  await page.goto("/login");
  const forgot = page.getByRole("link", { name: "Forgot password?" });
  await expect(forgot).toHaveAttribute("href", "/forgot-password");
  await page.getByRole("link", { name: "Admin / operator access" }).click();
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Forgot password?" })).toBeVisible();

  await page.goto("/forgot-password");
  await expect(page.locator(".auth-service-status")).toContainText("Reset email service configured");
  const identifier = page.getByLabel("Username, email or phone");
  await expect(identifier).toHaveAttribute("name", "identifier");
  await expect(identifier).toHaveAttribute("autocomplete", "username");
  await identifier.fill("existing-or-unknown@example.test");
  await page.getByRole("button", { name: "Send reset link" }).click();

  await expect(page.getByRole("heading", { name: "Check your email" })).toBeFocused();
  await expect(page.getByText("If an eligible account matches, a reset link has been sent.")).toBeVisible();
  expect(resetRequests).toEqual([{ identifier: "existing-or-unknown@example.test" }]);
  await expect(page.getByRole("link", { name: "Back to sign in" })).toHaveAttribute("href", "/login");
});

test("@public forgot-password distinguishes API readiness from reset-email capability", async ({ page }) => {
  let resetRequests = 0;
  await page.route("**/api/ready", route =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ready", password_reset_email_configured: false }),
    }),
  );
  await page.route("**/api/auth/password-reset/request/", route => {
    resetRequests += 1;
    return route.abort();
  });

  await page.goto("/forgot-password");
  await expect(page.locator(".auth-service-status")).toContainText("Reset email setup required");
  await expect(page.getByText("Reset links cannot be sent until the secure email provider is configured.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Email setup required" })).toBeDisabled();
  expect(resetRequests).toBe(0);
});

test("@public reset-password consumes a fragment token without storing or exposing it", async ({ page }) => {
  const token = "e2e-password-reset-token-that-is-never-stored";
  const payloads: Array<Record<string, unknown>> = [];
  await page.route("**/api/auth/password-reset/confirm/", async route => {
    payloads.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ message: "Password updated. All existing sessions have been signed out." }),
    });
  });

  await page.goto(`/reset-password#token=${token}`);
  await expect(page).toHaveURL(url => url.pathname === "/reset-password" && !url.hash && !url.search);
  const password = page.getByLabel("New password", { exact: true });
  const confirmation = page.getByLabel("Confirm new password", { exact: true });
  await expect(password).toHaveAttribute("name", "new-password");
  await expect(password).toHaveAttribute("autocomplete", "new-password");
  await expect(password).toHaveAttribute("minlength", "8");
  await expect(confirmation).toHaveAttribute("name", "confirm-password");
  await expect(confirmation).toHaveAttribute("autocomplete", "new-password");

  const newPassword = "Q7!mN2@pL8#xSecure";
  await password.fill(newPassword);
  await confirmation.fill(`${newPassword}-mismatch`);
  await expect(confirmation).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("button", { name: "Update password securely" })).toBeDisabled();
  await confirmation.fill(newPassword);
  await page.getByRole("button", { name: "Update password securely" }).click();

  await expect(page.getByRole("heading", { name: "Password updated" })).toBeFocused();
  expect(payloads).toEqual([{ token, password: newPassword }]);
  const storage = await page.evaluate(() => JSON.stringify({
    local: { ...window.localStorage },
    session: { ...window.sessionStorage },
  }));
  expect(storage).not.toContain(token);
  await expect(page.getByRole("link", { name: "Sign in with new password" })).toHaveAttribute("href", "/login");
});

test("@public reset-password rejects missing links without making an API request", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/auth/password-reset/confirm/", route => {
    requests += 1;
    return route.abort();
  });
  await page.goto("/reset-password");
  await expect(page.getByRole("heading", { name: "Reset link unavailable" })).toBeFocused();
  await expect(page.getByRole("link", { name: "Request a new link" })).toHaveAttribute("href", "/forgot-password");
  expect(requests).toBe(0);
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
  const strongPassword = "A9!bcdef";
  await expect(password).toHaveAttribute("minlength", "8");
  await expect(confirmation).toHaveAttribute("minlength", "8");
  await password.fill(strongPassword);
  await confirmation.fill(`${strongPassword}-different`);

  await expect(page.locator(".password-policy .password-policy--met")).toHaveCount(6);
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

test("@public MFA enrollment presents one scannable QR code with an accessible manual fallback", async ({ page }) => {
  await openMfaEnrollment(page);

  const section = page.locator('section[aria-labelledby="mfa-enrollment-title"]');
  await expect(section).toBeVisible();
  await expect(section.getByRole("heading", { name: "Scan QR code with your authenticator app" })).toHaveAttribute(
    "id",
    "mfa-enrollment-title",
  );
  const qrCode = section.getByRole("img", { name: "Scan QR code with your authenticator app" });
  await expect(qrCode).toHaveCount(1);
  await expect(qrCode).toHaveAttribute("aria-label", "Scan QR code with your authenticator app");
  await expect(qrCode.locator("title")).toHaveText("Scan QR code with your authenticator app");

  const manualFallback = section.getByText(/scan\? Use a setup key$/);
  await expect(manualFallback).toBeVisible();
  await manualFallback.click();
  const setupKey = section.getByLabel("Authenticator setup key");
  await expect(setupKey).toBeVisible();
  await expect(setupKey).toHaveText(enrollmentSecret);
  await expect(section.getByRole("button", { name: "Copy setup key" })).toBeVisible();
  await expect(section.getByRole("link", { name: "Open in authenticator app" })).toHaveAttribute("href", enrollmentUri);

  const code = page.getByLabel("Six-digit authenticator code");
  await expect(code).toBeVisible();
  await expect(code).toHaveAttribute("autocomplete", "one-time-code");
  await expect(code).toHaveAttribute("inputmode", "numeric");
  await expect(code).toHaveAttribute("pattern", "[0-9]{6}");
  await expect(code).toHaveAttribute("minlength", "6");
  await expect(code).toHaveAttribute("maxlength", "6");
  await expect(page.locator(".mfa-challenge-expiry[role='status']")).toContainText(/expires/i);
});

test("@public MFA enrollment rotates an exposed QR only after explicit confirmation", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "QR rotation transport contract");
  const replacementSecret = "NB2W45DFOIZA2YTBOI======NB2W45DF";
  const replacementUri = `otpauth://totp/SourceAI:e2e-admin?secret=${replacementSecret}&issuer=SourceAI&algorithm=SHA1&digits=6&period=30`;
  const restartPayloads: Array<Record<string, unknown>> = [];
  await page.route("**/api/auth/mfa/enroll/restart/", async route => {
    restartPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ secret: replacementSecret, otpauth_uri: replacementUri }),
    });
  });
  await openMfaEnrollment(page);

  const section = page.locator('section[aria-labelledby="mfa-enrollment-title"]');
  const qrCode = section.getByRole("img", { name: "Scan QR code with your authenticator app" });
  const originalQrFingerprint = await qrCode.locator("path").evaluateAll(paths =>
    paths.map(path => path.getAttribute("d") || "").join("|"),
  );
  await section.getByText(/scan\? Use a setup key$/).click();
  await expect(section.getByLabel("Authenticator setup key")).toHaveText(enrollmentSecret);
  await page.getByLabel("Six-digit authenticator code").fill("123456");

  await section.getByRole("button", { name: "Generate a new QR code" }).click();
  const confirmation = section.getByRole("group", { name: "Confirm new QR code generation" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toContainText("Replace the current QR code with a new one?");
  await confirmation.getByRole("button", { name: "Keep current QR code" }).click();
  await expect(confirmation).not.toBeVisible();
  expect(restartPayloads).toHaveLength(0);
  await expect(section.getByLabel("Authenticator setup key")).toHaveText(enrollmentSecret);

  await section.getByRole("button", { name: "Generate a new QR code" }).click();
  await confirmation.getByRole("button", { name: "Yes, generate new QR code" }).click();
  await expect.poll(() => restartPayloads.length).toBe(1);
  expect(restartPayloads).toEqual([{ mfa_token: "e2e-enrollment-token" }]);
  await expect(section.getByLabel("Authenticator setup key")).toHaveText(replacementSecret);
  await expect(section.getByRole("link", { name: "Open in authenticator app" })).toHaveAttribute("href", replacementUri);
  await expect(page.getByLabel("Six-digit authenticator code")).toHaveValue("");
  await expect(confirmation).not.toBeVisible();
  await expect.poll(async () => qrCode.locator("path").evaluateAll(paths =>
    paths.map(path => path.getAttribute("d") || "").join("|"),
  )).not.toBe(originalQrFingerprint);

  const browserStorage = await page.evaluate(() => JSON.stringify({
    local: { ...window.localStorage },
    session: { ...window.sessionStorage },
  }));
  expect(browserStorage).not.toContain(enrollmentSecret);
  expect(browserStorage).not.toContain(replacementSecret);
  expect(browserStorage).not.toContain("otpauth://");
});

test("@public expired MFA enrollment requires a fresh password-authenticated challenge", async ({ page }) => {
  await mockReadiness(page, true);
  const loginTokens = ["expired-enrollment-token", "fresh-enrollment-token"];
  const secrets = [
    "KRUGS4ZANFZSAYJAON2XEZJOORUXG5A1",
    "KRUGS4ZANFZSAYJAON2XEZJOORUXG5A2",
  ];
  let loginAttempt = 0;
  const startedTokens: string[] = [];
  const confirmationPayloads: Array<Record<string, unknown>> = [];

  await page.route("**/api/auth/login/", async route => {
    const token = loginTokens[Math.min(loginAttempt, loginTokens.length - 1)];
    loginAttempt += 1;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        mfa_required: true,
        mfa_enrollment_required: true,
        mfa_token: token,
        expires_in: 300,
      }),
    });
  });
  await page.route("**/api/auth/mfa/enroll/start/", async route => {
    const payload = route.request().postDataJSON() as { mfa_token: string };
    startedTokens.push(payload.mfa_token);
    const index = payload.mfa_token === loginTokens[0] ? 0 : 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        secret: secrets[index],
        otpauth_uri: `otpauth://totp/SourceAI:e2e-admin?secret=${secrets[index]}&issuer=SourceAI`,
      }),
    });
  });
  await page.route("**/api/auth/mfa/enroll/confirm/", async route => {
    confirmationPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "MFA challenge expired or already used" }),
    });
  });

  await page.goto("/login?portal=admin");
  await page.getByLabel("Username, email or phone").fill("e2e-admin");
  await page.getByLabel("Password", { exact: true }).fill("A9!Enrollment-Credential");
  await page.getByRole("button", { name: "Open admin dashboard" }).click();
  await expect(page.getByRole("img", { name: "Scan QR code with your authenticator app" })).toBeVisible();

  await page.getByLabel("Six-digit authenticator code").fill("123456");
  await page.getByRole("button", { name: "Enable and confirm MFA" }).click();
  const expiredAlert = page.locator(".mfa-expired-error[role='alert']");
  await expect(expiredAlert).toContainText(/(?:session|challenge).*expired|expired.*(?:session|challenge)/i);
  const restart = page.getByRole("button", { name: "Start sign-in again" });
  await expect(restart).toBeVisible();
  await restart.click();

  await expect(page).toHaveURL(url => url.pathname === "/login" && url.searchParams.get("portal") === "admin");
  await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
  await page.getByLabel("Password", { exact: true }).fill("A9!Enrollment-Credential");
  await page.getByRole("button", { name: "Open admin dashboard" }).click();
  await expect(page.getByRole("img", { name: "Scan QR code with your authenticator app" })).toBeVisible();
  await page.getByText(/scan\? Use a setup key$/).click();
  await expect(page.getByLabel("Authenticator setup key")).toHaveText(secrets[1]);

  expect(confirmationPayloads).toEqual([{ mfa_token: loginTokens[0], code: "123456" }]);
  expect(startedTokens).toEqual(loginTokens);
  expect(loginAttempt).toBe(2);
});

test("@public MFA enrollment fits the mobile viewport with the manual setup key expanded", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Mobile MFA enrollment layout contract");
  await openMfaEnrollment(page);
  await page.getByText(/scan\? Use a setup key$/).click();
  await expect(page.getByLabel("Authenticator setup key")).toBeVisible();

  const measurements = await page.evaluate(() => {
    const card = document.querySelector<HTMLElement>(".auth-card--single");
    const qr = document.querySelector<SVGElement>('[role="img"][aria-label="Scan QR code with your authenticator app"]');
    const setupKey = document.querySelector<HTMLElement>('[aria-label="Authenticator setup key"]');
    if (!card || !qr || !setupKey) return null;
    const visibleElements = Array.from(card.querySelectorAll<HTMLElement>("input, button, a, output, svg[role='img']"))
      .filter(element => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      })
      .map(element => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right };
      });
    const cardBox = card.getBoundingClientRect();
    const qrBox = qr.getBoundingClientRect();
    const keyBox = setupKey.getBoundingClientRect();
    return {
      viewportWidth: window.innerWidth,
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      card: { left: cardBox.left, right: cardBox.right },
      qr: { width: qrBox.width, height: qrBox.height, left: qrBox.left, right: qrBox.right },
      setupKey: { left: keyBox.left, right: keyBox.right, scrollWidth: setupKey.scrollWidth, width: keyBox.width },
      visibleElements,
    };
  });

  expect(measurements).not.toBeNull();
  expect(measurements!.overflow).toBeLessThanOrEqual(1);
  expect(measurements!.card.left).toBeGreaterThanOrEqual(-0.5);
  expect(measurements!.card.right).toBeLessThanOrEqual(measurements!.viewportWidth + 0.5);
  expect(measurements!.qr.width).toBeGreaterThan(0);
  expect(Math.abs(measurements!.qr.width - measurements!.qr.height)).toBeLessThanOrEqual(1);
  expect(measurements!.qr.left).toBeGreaterThanOrEqual(-0.5);
  expect(measurements!.qr.right).toBeLessThanOrEqual(measurements!.viewportWidth + 0.5);
  expect(measurements!.setupKey.left).toBeGreaterThanOrEqual(-0.5);
  expect(measurements!.setupKey.right).toBeLessThanOrEqual(measurements!.viewportWidth + 0.5);
  expect(measurements!.visibleElements.every(element =>
    element.left >= -0.5 && element.right <= measurements!.viewportWidth + 0.5,
  )).toBe(true);
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
  await expect(page.locator(".auth-service-status")).toHaveCount(0);
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
  await expectMobileAuthPageFits(page, "/forgot-password");
});
