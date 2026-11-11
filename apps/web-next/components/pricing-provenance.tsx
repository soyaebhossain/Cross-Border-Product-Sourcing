"use client";

import type { PriceComponent, QuotePricing } from "../lib/api";
import { formatDateTime } from "../lib/format";

const COMPONENT_LABELS: Record<string, { en: string; bn: string }> = {
  supplier_offer: { en: "Supplier price", bn: "সাপ্লায়ারের দাম" },
  fx_rate: { en: "Exchange rate", bn: "বিনিময় হার" },
  freight: { en: "Freight", bn: "শিপিং খরচ" },
  customs_duty: { en: "Customs duty", bn: "কাস্টমস শুল্ক" },
};

const SOURCE_LABELS: Record<string, { en: string; bn: string }> = {
  api: { en: "Live feed", bn: "লাইভ ফিড" },
  admin: { en: "Verified by SourceAI team", bn: "SourceAI টিম যাচাই করেছে" },
  supplier_quote: { en: "Supplier quotation", bn: "সাপ্লায়ারের কোটেশন" },
  csv_import: { en: "Imported dataset", bn: "আমদানি করা ডেটাসেট" },
  seeded: { en: "Reference dataset", bn: "রেফারেন্স ডেটাসেট" },
};

const STALE_REASONS: Record<string, { en: string; bn: string }> = {
  unverified: { en: "Never verified", bn: "কখনো যাচাই হয়নি" },
  older_than_policy: { en: "Older than allowed", bn: "নির্ধারিত সময়ের চেয়ে পুরনো" },
  validity_ended: { en: "Validity ended", bn: "মেয়াদ শেষ" },
};

function componentTitle(item: PriceComponent, bn: boolean, intlLocale: string): string {
  const label = COMPONENT_LABELS[item.component]?.[bn ? "bn" : "en"] ?? item.component;
  if (item.component === "fx_rate" && item.currency) {
    const rate = Number(item.rate_to_bdt);
    const shown = Number.isFinite(rate) ? new Intl.NumberFormat(intlLocale, { maximumFractionDigits: 4 }).format(rate) : "";
    return `${label} (1 ${item.currency} = ৳${shown})`;
  }
  if (item.component === "freight" && item.method) return `${label} (${item.method})`;
  return label;
}

function maxAgeText(hours: number, bn: boolean): string {
  if (hours >= 48 && hours % 24 === 0) {
    const days = hours / 24;
    return bn ? `${days} দিন` : `${days} days`;
  }
  return bn ? `${hours} ঘণ্টা` : `${hours} hours`;
}

export function PricingProvenance({ pricing, bn, intlLocale }: { pricing?: QuotePricing | null; bn: boolean; intlLocale: string }) {
  if (!pricing || !Array.isArray(pricing.components) || pricing.components.length === 0) return null;
  const verified = pricing.status === "verified";
  const usesLiveFx = pricing.components.some(item => item.component === "fx_rate" && item.source === "api");
  return (
    <article className="form-card pricing-provenance" aria-labelledby="pricing-provenance-title">
      <div className="section__header">
        <div>
          <p className="eyebrow">{bn ? "দামের উৎস ও সময়" : "Price sources and freshness"}</p>
          <h2 id="pricing-provenance-title">
            {verified
              ? (bn ? "সব দাম সাম্প্রতিক যাচাই করা" : "All prices recently verified")
              : (bn ? "আনুমানিক দাম" : "Indicative prices")}
          </h2>
        </div>
        <span className={`admin-status admin-status--${verified ? "verified" : "pending"}`}>
          {verified ? (bn ? "যাচাইকৃত" : "Verified") : (bn ? "আবার যাচাই প্রয়োজন" : "Re-verify before ordering")}
        </span>
      </div>
      {!verified ? (
        <p className="pricing-provenance__note">
          {bn
            ? "নিচের কিছু দামের তথ্য নির্ধারিত সময়ের চেয়ে পুরনো বা যাচাই করা হয়নি। এই হিসাব রেফারেন্স হিসেবে দেখুন; অর্ডারের আগে সিস্টেম বর্তমান তথ্য দিয়ে খরচ আবার হিসাব করবে।"
            : "Some price inputs below are older than their allowed age or were never verified. Treat this total as a reference; the system recalculates the landed cost with current data before an order is accepted."}
        </p>
      ) : null}
      <ul className="pricing-provenance__list">
        {pricing.components.map(item => {
          const source = SOURCE_LABELS[item.source]?.[bn ? "bn" : "en"] ?? item.source;
          return (
            <li key={item.component} className={item.fresh ? "" : "pricing-provenance__item--stale"}>
              <div>
                <strong>{componentTitle(item, bn, intlLocale)}</strong>
                <small>
                  {source}
                  {item.reference && /^https?:\/\//.test(item.reference) ? (
                    <> · <a href={item.reference} target="_blank" rel="noopener noreferrer">{bn ? "উৎস" : "source"}</a></>
                  ) : item.reference ? ` · ${item.reference}` : ""}
                </small>
              </div>
              <div className="pricing-provenance__status">
                <span>
                  {item.verified_at
                    ? `${bn ? "যাচাই" : "Verified"}: ${formatDateTime(item.verified_at, intlLocale)}`
                    : (bn ? "যাচাইয়ের সময় নেই" : "No verification date")}
                </span>
                <small>
                  {item.fresh
                    ? (bn ? `সর্বোচ্চ বয়স ${maxAgeText(item.max_age_hours, true)} — ঠিক আছে` : `Within ${maxAgeText(item.max_age_hours, false)} limit`)
                    : item.stale_reasons.map(reason => STALE_REASONS[reason]?.[bn ? "bn" : "en"] ?? reason).join(", ")}
                </small>
              </div>
            </li>
          );
        })}
      </ul>
      <small className="pricing-provenance__footer">
        {bn ? "হিসাবের সময়" : "Calculated"}: {formatDateTime(pricing.calculated_at, intlLocale)}
        {usesLiveFx ? (
          <> · <a href="https://www.exchangerate-api.com" target="_blank" rel="noopener noreferrer">Rates By Exchange Rate API</a></>
        ) : null}
      </small>
    </article>
  );
}
