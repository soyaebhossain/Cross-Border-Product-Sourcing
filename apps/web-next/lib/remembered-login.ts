export type LoginPortal = "customer" | "admin";

const STORAGE_KEY = "sourceai-remembered-login-v1";
const MAX_IDENTIFIER_LENGTH = 320;

type RememberedLogins = Partial<Record<LoginPortal, string>>;

function readRememberedLogins(): RememberedLogins {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const values = parsed as Record<string, unknown>;
    return {
      ...(typeof values.customer === "string" ? { customer: values.customer.slice(0, MAX_IDENTIFIER_LENGTH) } : {}),
      ...(typeof values.admin === "string" ? { admin: values.admin.slice(0, MAX_IDENTIFIER_LENGTH) } : {}),
    };
  } catch {
    return {};
  }
}

export function getRememberedIdentifier(portal: LoginPortal): string {
  return readRememberedLogins()[portal] || "";
}

export function updateRememberedIdentifier(portal: LoginPortal, identifier: string, remember: boolean): void {
  if (typeof window === "undefined") return;
  try {
    const remembered = readRememberedLogins();
    const normalized = identifier.trim().slice(0, MAX_IDENTIFIER_LENGTH);
    if (remember && normalized) remembered[portal] = normalized;
    else delete remembered[portal];

    if (remembered.customer || remembered.admin) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(remembered));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage may be unavailable in private or locked-down browser contexts.
  }
}
