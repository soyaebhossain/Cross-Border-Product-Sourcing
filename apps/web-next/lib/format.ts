export function formatAmount(value: string | number | null | undefined, locale = "en-US"): string {
  if (value === null || value === undefined || value === "") return "—";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatBdt(value: string | number | null | undefined, locale = "en-BD"): string {
  return formatCurrency(value, "BDT", locale);
}

export function formatCurrency(
  value: string | number | null | undefined,
  currency: "BDT" | "USD" = "BDT",
  locale = "en-BD",
): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    currencyDisplay: "code",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatDateTime(
  value: string | Date | null | undefined,
  locale = "en-BD",
  options?: Intl.DateTimeFormatOptions,
): string {
  if (!value) return "—";
  const normalized = typeof value === "string" && /^\d{4}-\d{2}-\d{2}T[\d:.]+$/.test(value) ? `${value}Z` : value;
  const date = normalized instanceof Date ? normalized : new Date(normalized);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Dhaka",
    dateStyle: "medium",
    timeStyle: "short",
    ...options,
  }).format(date);
}
