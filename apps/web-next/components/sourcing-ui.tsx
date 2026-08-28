"use client";

import { useLocale } from "../lib/locale-context";
import { sourcingText } from "../lib/sourcing-copy";

export function PriceDisplay({ amount, currency = "USD", compact = false }: { amount: number | null | undefined; currency?: string; compact?: boolean }) {
  const { locale } = useLocale();
  if (amount === null || amount === undefined) return <span className="price-display price-display--pending">{locale === "bn" ? "মূল্য কোটে জানানো হবে" : "Price on request"}</span>;
  const formatted = new Intl.NumberFormat(locale === "bn" ? "bn-BD" : "en-US", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
  return <span className={compact ? "price-display price-display--compact" : "price-display"}><small>{sourcingText(locale, "from")}</small> {formatted}</span>;
}

export function RiskBadge({ level }: { level: string | null | undefined }) {
  const normalized = (level || "Pending").toLowerCase();
  const { locale } = useLocale();
  const label = normalized === "low" ? (locale === "bn" ? "কম ঝুঁকি" : "Low risk") : normalized === "medium" ? (locale === "bn" ? "মাঝারি ঝুঁকি" : "Medium risk") : normalized === "high" ? (locale === "bn" ? "উচ্চ ঝুঁকি" : "High risk") : (locale === "bn" ? "ঝুঁকি কোটে যাচাই হবে" : "Risk pending quote");
  return <span className={`risk-badge-ui risk-badge-ui--${normalized}`} aria-label={label}><span aria-hidden>●</span>{label}</span>;
}

export function TrustBadge({ children, explanation }: { children: React.ReactNode; explanation: string }) {
  return <span className="trust-badge-ui" title={explanation} tabIndex={0} aria-label={`${children}. ${explanation}`}><span aria-hidden>✓</span>{children}</span>;
}

export function QuantitySelector({ value, min = 1, max = 100_000, onChange, label }: { value: number; min?: number; max?: number; onChange: (value: number) => void; label: string }) {
  const { locale } = useLocale();
  const update = (next: number) => onChange(Math.min(max, Math.max(min, Number.isFinite(next) ? Math.round(next) : min)));
  return <div className="quantity-selector" aria-label={label}>
    <button type="button" onClick={() => update(value - 1)} disabled={value <= min} aria-label={`${label}: ${locale === "bn" ? "কমান" : "decrease"}`}>−</button>
    <input type="number" min={min} max={max} value={value} onChange={(event) => update(Number(event.target.value))} aria-label={label} />
    <button type="button" onClick={() => update(value + 1)} disabled={value >= max} aria-label={`${label}: ${locale === "bn" ? "বাড়ান" : "increase"}`}>+</button>
  </div>;
}
