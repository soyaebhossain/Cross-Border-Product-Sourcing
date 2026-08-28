import { expect, test, type Page } from "@playwright/test";

const profileFixture = {
  user_id: 27,
  username: "tamanna",
  email: "tamanna@example.com",
  phone: null,
  full_name: "Tamanna Rahman",
  company: {
    name: "Source Partners Ltd",
    registration_number: "BD-C-2026-1042",
    tax_identifier: "TIN-9021042",
  },
  preferences: {
    language: "en",
    currency: "BDT",
    timezone: "Asia/Dhaka",
  },
};

const profileFields = [
  "Full name",
  "Company name",
  "Registration number",
  "Tax identifier",
  "Language",
  "Currency",
  "Timezone (IANA)",
] as const;

async function mockCustomerProfile(page: Page) {
  await page.route("**/api/**", async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;

    if (pathname === "/api/auth/me/") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: profileFixture.user_id,
          username: profileFixture.username,
          email: profileFixture.email,
          role: "customer",
        }),
      });
    }

    if (pathname === "/api/account/profile/") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(profileFixture),
      });
    }

    if (pathname === "/api/account/addresses/") {
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    }

    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Profile layout test fixture" }),
    });
  });
}

test("@public customer profile form stays accessible and aligned across responsive widths", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  await mockCustomerProfile(page);

  const widths = testInfo.project.name === "mobile-chromium"
    ? [360, 390, 680, 768]
    : [1024, 1225, 1440];

  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/account/profile", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Profile and addresses" })).toBeVisible();
    await expect(page.locator(".account-profile-form")).toBeVisible();

    for (const field of profileFields) {
      const control = field === "Language"
        ? page.getByRole("combobox", { name: field, exact: true })
        : page.getByRole("textbox", { name: field, exact: true });
      await expect(control, `${field} is associated with exactly one form control at ${width}px`).toHaveCount(1);
      await expect(control).toBeVisible();
    }

    const layout = await page.evaluate((fieldNames) => {
      const tolerance = 1;
      const form = document.querySelector<HTMLFormElement>(".account-profile-form")!;
      const panel = form.closest<HTMLElement>(".account-panel")!;
      const accountShell = document.querySelector<HTMLElement>(".account-shell")!;
      const pageHeader = document.querySelector<HTMLElement>(".account-page-header")!;
      const header = document.querySelector<HTMLElement>(".site-header--authenticated")!;
      const nav = header.querySelector<HTMLElement>(".site-header__nav")!;
      const action = header.querySelector<HTMLElement>(".site-header__action")!;
      const menu = header.querySelector<HTMLButtonElement>(".mobile-menu")!;
      const sidebar = document.querySelector<HTMLElement>(".account-sidebar")!;
      const mobileNav = document.querySelector<HTMLElement>(".account-mobile-nav")!;
      const visible = (element: Element) => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      };
      const box = (element: Element) => {
        const rect = element.getBoundingClientRect();
        return {
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        };
      };

      const controls = fieldNames.map(name => {
        const labels = Array.from(document.querySelectorAll<HTMLLabelElement>("label"));
        const label = labels.find(item => item.textContent?.trim().startsWith(name))!;
        const control = label.control as HTMLInputElement | HTMLSelectElement | null;
        const labelText = label.querySelector<HTMLElement>("span")!;
        return {
          name,
          labelCount: control?.labels?.length || 0,
          label: box(label),
          labelText: box(labelText),
          control: control ? box(control) : null,
        };
      });

      const controlOverlaps: string[] = [];
      for (let leftIndex = 0; leftIndex < controls.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < controls.length; rightIndex += 1) {
          const left = controls[leftIndex].control;
          const right = controls[rightIndex].control;
          if (!left || !right) continue;
          const overlapWidth = Math.min(left.right, right.right) - Math.max(left.left, right.left);
          const overlapHeight = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
          if (overlapWidth > tolerance && overlapHeight > tolerance) {
            controlOverlaps.push(`${controls[leftIndex].name} <> ${controls[rightIndex].name}`);
          }
        }
      }

      const formBox = box(form);
      const panelBox = box(panel);
      const pageHeaderChildren = Array.from(pageHeader.children).filter(visible).map(box);
      const pageHeaderOverlap = pageHeaderChildren.length > 1
        ? Math.min(pageHeaderChildren[0].right, pageHeaderChildren[1].right) - Math.max(pageHeaderChildren[0].left, pageHeaderChildren[1].left) > tolerance
          && Math.min(pageHeaderChildren[0].bottom, pageHeaderChildren[1].bottom) - Math.max(pageHeaderChildren[0].top, pageHeaderChildren[1].top) > tolerance
        : false;

      return {
        viewportWidth: window.innerWidth,
        documentOverflow: document.documentElement.scrollWidth - window.innerWidth,
        shell: box(accountShell),
        form: formBox,
        panel: panelBox,
        controls,
        controlOverlaps,
        pageHeaderOverlap,
        header: box(header),
        headerNavVisible: visible(nav),
        headerActionVisible: visible(action),
        mobileMenuVisible: visible(menu),
        sidebarVisible: visible(sidebar),
        mobileAccountNavVisible: visible(mobileNav),
      };
    }, profileFields);

    expect.soft(layout.documentOverflow, `${width}px document overflow`).toBeLessThanOrEqual(1);
    expect.soft(layout.shell.left, `${width}px account shell left`).toBeGreaterThanOrEqual(-1);
    expect.soft(layout.shell.right, `${width}px account shell right`).toBeLessThanOrEqual(width + 1);
    expect.soft(layout.panel.left, `${width}px profile panel left`).toBeGreaterThanOrEqual(-1);
    expect.soft(layout.panel.right, `${width}px profile panel right`).toBeLessThanOrEqual(width + 1);
    expect.soft(layout.controlOverlaps, `${width}px profile control overlaps`).toEqual([]);
    expect.soft(layout.pageHeaderOverlap, `${width}px heading/action overlap`).toBe(false);

    const controlHeights = layout.controls.map(item => item.control?.height || 0);
    expect.soft(Math.min(...controlHeights), `${width}px minimum control height`).toBeGreaterThanOrEqual(40);
    expect.soft(Math.max(...controlHeights) - Math.min(...controlHeights), `${width}px control-height variance`).toBeLessThanOrEqual(2);

    for (const field of layout.controls) {
      expect.soft(field.labelCount, `${field.name} native label association at ${width}px`).toBeGreaterThan(0);
      expect.soft(field.control, `${field.name} control measurement at ${width}px`).not.toBeNull();
      if (!field.control) continue;
      expect.soft(field.labelText.bottom, `${field.name} label position at ${width}px`).toBeLessThanOrEqual(field.control.top + 1);
      expect.soft(field.control.left, `${field.name} control left at ${width}px`).toBeGreaterThanOrEqual(layout.form.left - 1);
      expect.soft(field.control.right, `${field.name} control right at ${width}px`).toBeLessThanOrEqual(layout.form.right + 1);
      expect.soft(field.control.width, `${field.name} usable width at ${width}px`).toBeGreaterThanOrEqual(width <= 390 ? 240 : 150);
    }

    if (width <= 900) {
      expect.soft(layout.sidebarVisible, `${width}px desktop account sidebar`).toBe(false);
      expect.soft(layout.mobileAccountNavVisible, `${width}px mobile account navigation`).toBe(true);
    } else {
      expect.soft(layout.sidebarVisible, `${width}px desktop account sidebar`).toBe(true);
      expect.soft(layout.mobileAccountNavVisible, `${width}px mobile account navigation`).toBe(false);
    }

    if (width <= 980) {
      expect.soft(layout.mobileMenuVisible, `${width}px shared header menu`).toBe(true);
      expect.soft(layout.headerNavVisible, `${width}px collapsed primary navigation`).toBe(false);
      expect.soft(layout.headerActionVisible, `${width}px collapsed header actions`).toBe(false);
    } else {
      expect.soft(layout.mobileMenuVisible, `${width}px desktop menu trigger`).toBe(false);
      expect.soft(layout.headerNavVisible, `${width}px desktop primary navigation`).toBe(true);
      expect.soft(layout.headerActionVisible, `${width}px desktop header actions`).toBe(true);
    }

    if (width >= 1181) {
      expect.soft(layout.header.height, `${width}px single-row desktop header height`).toBeLessThanOrEqual(76);
    }
  }
});
