"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useState } from "react";
import { getCheapestCountryRecommendationWithAi, type CheapestCountryRecommendation } from "../lib/api";
import { localizedAiItems, localizedAiSummary } from "../lib/ai-explanation-locale";
import { formatBdt } from "../lib/format";
import { useLocale } from "../lib/locale-context";
import { localizedRecommendationText } from "../lib/sourcing-copy";

export function SourcingWorkspace({ variantId }: { variantId: number }) {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const [qty, setQty] = useState(10);
  const [weights, setWeights] = useState<Record<string, number>>({ price: 35, quality: 20, delivery: 15, reliability: 15, risk: 15 });
  const [data, setData] = useState<CheapestCountryRecommendation | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const names = bn
    ? { price: "মূল্য", quality: "গুণমান", delivery: "ডেলিভারি", reliability: "নির্ভরযোগ্যতা", risk: "কম ঝুঁকি" }
    : { price: "Price", quality: "Quality", delivery: "Delivery", reliability: "Reliability", risk: "Low risk" };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    setData(null);
    const timer = setTimeout(() => {
      getCheapestCountryRecommendationWithAi({ variant_id: variantId, qty, weights, language: locale })
        .then((result) => {
          if (!active) return;
          setData(result);
          setSelectedIndex(0);
        })
        .catch(() => {
          if (active) setError(true);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 700);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [variantId, qty, weights, refreshKey, locale]);

  const selected = data?.recommendations[selectedIndex];
  const aiExplanation = data?.ai_explanation;
  const aiSummary = aiExplanation
    ? localizedAiSummary(
        aiExplanation,
        locale,
        bn ? "দেশভিত্তিক সুপারিশের সারাংশ এখন পাওয়া যাচ্ছে না।" : "The country recommendation summary is not available yet.",
      )
    : "";
  const aiAdvantages = aiExplanation
    ? localizedAiItems(aiExplanation.advantages, locale, bn ? "কোনো সুবিধার তথ্য দেওয়া হয়নি।" : "No advantages were supplied.", aiExplanation.language)
    : [];
  const aiRisks = aiExplanation
    ? localizedAiItems(aiExplanation.risks, locale, bn ? "অতিরিক্ত ঝুঁকি শনাক্ত হয়নি।" : "No additional risk was identified.", aiExplanation.language)
    : [];
  const aiRecommendedChecks = aiExplanation
    ? localizedAiItems(aiExplanation.recommended_checks, locale, bn ? "কোনো যাচাইয়ের তথ্য দেওয়া হয়নি।" : "No checks were supplied.", aiExplanation.language)
    : [];
  const quoteHref = (selected
    ? `/quote?variant=${variantId}&qty=${qty}&country=${encodeURIComponent(selected.country.code)}&mode=${encodeURIComponent(selected.mode)}`
    : `/quote?variant=${variantId}&qty=${qty}`) as Route;
  const riskLabel = (level: string) => {
    if (!bn) return `${level} risk`;
    if (level.toLowerCase() === "low") return "কম ঝুঁকি";
    if (level.toLowerCase() === "medium") return "মাঝারি ঝুঁকি";
    return "উচ্চ ঝুঁকি";
  };

  return (
    <section className="workspace">
      <div className="workspace-head">
        <div>
          <span className="market-kicker">{bn ? "স্বয়ংক্রিয় দেশভিত্তিক সুপারিশ" : "Automated country recommendation"}</span>
          <h2>{bn ? "কোন দেশ থেকে সোর্সিং বেশি লাভজনক?" : "Which country is the best sourcing option?"}</h2>
          <p>{bn ? "দাম, ল্যান্ডেড কস্ট, ডেলিভারি, সাপ্লায়ারের নির্ভরযোগ্যতা ও ঝুঁকি দিয়ে র‍্যাঙ্কিং হয়; Ollama ফলটির ব্যাখ্যা দেয়।" : "Rankings use price, landed cost, delivery, supplier reliability, and risk; Ollama explains the result."}</p>
        </div>
        <label className="qty-control">{bn ? "পরিমাণ" : "Quantity"}<input type="number" min="1" value={qty} onChange={(event) => setQty(Math.max(1, Number(event.target.value) || 1))} /></label>
      </div>
      <div className="weight-grid">
        {Object.entries(names).map(([key, label]) => (
          <label key={key}>
            <span>{label}<b>{weights[key]}%</b></span>
            <input type="range" min="0" max="100" value={weights[key]} onChange={(event) => setWeights((value) => ({ ...value, [key]: Number(event.target.value) }))} />
          </label>
        ))}
      </div>

      {loading ? <div className="workspace-loading" role="status">{bn ? "দেশভিত্তিক খরচ হিসাব করে AI ব্যাখ্যা তৈরি হচ্ছে…" : "Calculating country costs and preparing the AI explanation…"}</div> : null}
      {error ? (
        <div className="market-empty" role="alert">
          <strong>{bn ? "সুপারিশ সেবা এখন পাওয়া যাচ্ছে না।" : "Recommendation service is unavailable."}</strong>
          <button className="market-button" type="button" onClick={() => setRefreshKey((value) => value + 1)}>{bn ? "আবার চেষ্টা করুন" : "Try again"}</button>
        </div>
      ) : null}

      {data && !error ? (
        <div className="supplier-table">
          {data.recommendations.slice(0, 5).map((item, index) => (
            <article
              role="button"
              tabIndex={0}
              aria-pressed={selectedIndex === index}
              onClick={() => setSelectedIndex(index)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedIndex(index);
                }
              }}
              className={`supplier-option${index === 0 ? " supplier-option--best" : ""}${selectedIndex === index ? " supplier-option--selected" : ""}`}
              key={`${item.country.code}-${item.mode}`}
            >
              <div className="supplier-rank">#{item.rank}</div>
              <div><strong>{item.selected_offer.seller_name}</strong><span>{item.country.name} · {item.mode}</span></div>
              <div><small>{bn ? "ল্যান্ডেড কস্ট" : "Landed cost"}</small><strong>{formatBdt(item.estimated_total_bdt, intlLocale)}</strong></div>
              <div><small>{bn ? "ডেলিভারি" : "Delivery"}</small><strong>{item.eta.min_days}–{item.eta.max_days} {bn ? "দিন" : "days"}</strong></div>
              <div><small>{bn ? "স্কোর" : "Score"}</small><strong>{Number(item.score).toFixed(1)}/100</strong></div>
              <span className={`risk-badge risk-badge--${item.risk_level.toLowerCase()}`}>{riskLabel(item.risk_level)}</span>
              <p>{localizedRecommendationText(locale, item.reason)}{item.weaknesses.length ? ` ${bn ? "সতর্কতা" : "Watch"}: ${item.weaknesses.map((value) => localizedRecommendationText(locale, value)).join(", ")}.` : ""}</p>
              {index === 0 ? <span className="best-badge">{bn ? "সুপারিশকৃত" : "Recommended"}</span> : selectedIndex === index ? <span className="selected-badge">{bn ? "নির্বাচিত" : "Selected"}</span> : null}
            </article>
          ))}
        </div>
      ) : null}

      {data?.ai_explanation && !error ? (
        <article className="workspace-ai" aria-labelledby="country-ai-title">
          <div className="workspace-ai__header">
            <div>
              <span className="market-kicker">{bn ? "AI-সহায়িত ব্যাখ্যা" : "AI-assisted explanation"}</span>
              <h3 id="country-ai-title">{bn ? "কেন এই দেশটি সুপারিশ করা হয়েছে" : "Why this country is recommended"}</h3>
            </div>
            <span className={`workspace-ai__status${data.ai_metadata?.automation_available ? " workspace-ai__status--active" : ""}`}>
              {data.ai_metadata?.automation_available ? `Ollama · ${data.ai_metadata.model || "local model"}` : (bn ? "নির্ধারিত fallback" : "Deterministic fallback")}
            </span>
          </div>
          <p className="workspace-ai__summary">{aiSummary}</p>
          <div className="workspace-ai__grid">
            <div><strong>{bn ? "সুবিধা" : "Advantages"}</strong><ul>{aiAdvantages.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><strong>{bn ? "ঝুঁকি" : "Risks"}</strong><ul>{aiRisks.map((item) => <li key={item}>{item}</li>)}</ul></div>
            <div><strong>{bn ? "যা যাচাই করবেন" : "Recommended checks"}</strong><ul>{aiRecommendedChecks.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </div>
          <small>{bn ? "র‍্যাঙ্কিং ও সব আর্থিক হিসাব server-এর deterministic sourcing engine করে; AI শুধু ব্যাখ্যা দেয়।" : "The server's deterministic sourcing engine calculates rankings and all monetary values; AI only explains the result."}{data.ai_explanation.human_review_required ? (bn ? " মানুষের পর্যালোচনা প্রয়োজন।" : " Human review is required.") : ""}</small>
        </article>
      ) : null}

      <div className="workspace-actions">
        <Link className="market-button" href={quoteHref}>{bn ? "নির্বাচিত কোট চান ও সংরক্ষণ করুন" : "Request and save selected quote"}</Link>
        <Link href="/account/saved-quotes">{bn ? "সংরক্ষিত কোট তুলনা করুন" : "Compare saved quotes"} →</Link>
      </div>
    </section>
  );
}
