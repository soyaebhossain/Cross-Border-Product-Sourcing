"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { getCountries, getProducts, quoteProductWithAi, saveQuote, type Country, type Product, type QuoteResponse } from "../../lib/api";
import { localizedAiItems, localizedAiSummary } from "../../lib/ai-explanation-locale";
import { formatBdt } from "../../lib/format";
import { useLocale } from "../../lib/locale-context";

export default function QuotePage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const [products, setProducts] = useState<Product[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null);
  const [form, setForm] = useState({ qty: 1, country: "CN", mode: "LOCAL", delivery_type: "DOOR" });
  const [response, setResponse] = useState<QuoteResponse | null>(null);
  const [savedQuoteId, setSavedQuoteId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [catalogPreview, setCatalogPreview] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedVariant = Number(params.get("variant")) || null;
    const rawRequestedQty = Number(params.get("qty"));
    const requestedQty = Number.isFinite(rawRequestedQty)
      ? Math.min(100_000, Math.max(1, Math.round(rawRequestedQty)))
      : 1;
    const requestedCountry = params.get("country");
    const requestedMode = params.get("mode");
    setForm((prev) => ({ ...prev, qty: requestedQty, country: requestedCountry || prev.country, mode: requestedMode || prev.mode }));
    getProducts().then((items) => {
      setProducts(items);
      setCatalogPreview(items.some(item => item.catalog_source === "snapshot"));
      if (requestedVariant) {
        const product = items.find((item) => item.variants.some((variant) => variant.id === requestedVariant));
        if (product) {
          setSelectedProductId(product.id);
          setSelectedVariantId(requestedVariant);
        }
      }
    }).catch(() => {});
    getCountries().then(setCountries).catch(() => {});
  }, []);

  const selectedProduct = products.find((product) => product.id === selectedProductId);
  const variants = selectedProduct?.variants || [];

  useEffect(() => {
    if (selectedProduct && selectedProduct.variants.length > 0) {
      setSelectedVariantId((prev) => prev || selectedProduct.variants[0].id);
    }
  }, [selectedProduct]);

  useEffect(() => {
    // A generated explanation belongs to the language used in its request.
    // Clear it on a locale switch so the page never presents stale mixed-language output.
    setResponse(null);
    setSavedQuoteId(null);
  }, [locale]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!selectedVariantId) {
      setError("Select a product variant before requesting a quote.");
      return;
    }
    setLoading(true);
    try {
      const result = await quoteProductWithAi({
        variant_id: selectedVariantId,
        country: form.country,
        mode: form.mode,
        qty: Number(form.qty) || 1,
        delivery_type: form.delivery_type,
        language: locale,
      });
      setResponse(result);
      setSavedQuoteId(null);
    } catch {
      setResponse(null);
      setError("Quote request failed. Please try a different product, country, or quantity.");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!response || !selectedVariantId) return;
    try {
      const savedQuote = await saveQuote({ variant_id: selectedVariantId, country: form.country, mode: form.mode, qty: form.qty, delivery_type: form.delivery_type, response });
      setSavedQuoteId(savedQuote.id);
    } catch { setError("Login is required to save this quote."); }
  };

  const summary = useMemo(() => {
    if (!response?.breakdown) return null;
    return response.breakdown;
  }, [response]);
  const aiExplanation = response?.ai_explanation;
  const aiMetadata = response?.ai_metadata;
  const aiSummary = aiExplanation
    ? localizedAiSummary(
        aiExplanation,
        locale,
        bn ? "সোর্সিং সুপারিশের সারাংশ এখন পাওয়া যাচ্ছে না।" : "The sourcing recommendation summary is not available yet.",
      )
    : "";
  const aiAdvantages = aiExplanation
    ? localizedAiItems(aiExplanation.advantages, locale, bn ? "কোনো সুবিধার তথ্য দেওয়া হয়নি।" : "No advantages were supplied.", aiExplanation.language)
    : [];
  const aiRisks = aiExplanation
    ? localizedAiItems(aiExplanation.risks, locale, bn ? "অতিরিক্ত ঝুঁকি শনাক্ত হয়নি।" : "No additional risk was identified.", aiExplanation.language)
    : [];
  const aiMissingInformation = aiExplanation
    ? localizedAiItems(aiExplanation.missing_information, locale, bn ? "অনুপস্থিত তথ্যের বিবরণ দেওয়া হয়নি।" : "No missing-information details were supplied.", aiExplanation.language)
    : [];
  const aiRecommendedChecks = aiExplanation
    ? localizedAiItems(aiExplanation.recommended_checks, locale, bn ? "কোনো যাচাইয়ের তথ্য দেওয়া হয়নি।" : "No checks were supplied.", aiExplanation.language)
    : [];

  return (
    <main className="shell shell--narrow">
      <div className="section">
        {catalogPreview ? (
          <div className="catalog-preview-notice" role="status">
            <strong>Catalog preview</strong>
            <span>Products and sourcing lanes are available to browse. Quote controls are read-only until the secure account service is online.</span>
          </div>
        ) : null}
        <div className="section__header">
          <div>
            <p className="eyebrow">Quote</p>
            <h1>Request a sourcing estimate</h1>
          </div>
        </div>

        <form className="form-card" onSubmit={handleSubmit}>
          <fieldset className="form-grid" disabled={catalogPreview}>
            <div className="form-field">
              <label>Product</label>
              <select
                value={selectedProductId ?? ""}
                onChange={(event) => setSelectedProductId(Number(event.target.value) || null)}
                className="input-field"
              >
                <option value="">Select a product</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} • {product.category.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label>Variant</label>
              <select
                value={selectedVariantId ?? ""}
                onChange={(event) => setSelectedVariantId(Number(event.target.value) || null)}
                className="input-field"
              >
                <option value="">Select variant</option>
                {variants.map((variant) => (
                  <option key={variant.id} value={variant.id}>
                    {variant.variant_name || variant.sku || `Variant ${variant.id}`} • {variant.weight_kg} kg
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label>Quantity</label>
              <input
                type="number"
                min={1}
                max={100000}
                value={form.qty}
                onChange={(event) => setForm((prev) => ({
                  ...prev,
                  qty: Math.min(100_000, Math.max(1, Math.round(Number(event.target.value) || 1))),
                }))}
                className="input-field"
              />
            </div>

            <div className="form-field">
              <label>Country</label>
              <select
                value={form.country}
                onChange={(event) => setForm((prev) => ({ ...prev, country: event.target.value }))}
                className="input-field"
              >
                {countries.map((country) => (
                  <option key={country.code} value={country.code}>
                    {country.name} ({country.code})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label>Mode</label>
              <select
                value={form.mode}
                onChange={(event) => setForm((prev) => ({ ...prev, mode: event.target.value }))}
                className="input-field"
              >
                <option value="LOCAL">Local (air)</option>
                <option value="BULK">Bulk (sea)</option>
              </select>
            </div>

            <div className="form-field">
              <label>Delivery</label>
              <select
                value={form.delivery_type}
                onChange={(event) => setForm((prev) => ({ ...prev, delivery_type: event.target.value }))}
                className="input-field"
              >
                <option value="DOOR">Door delivery</option>
                <option value="PICKUP">Pickup</option>
              </select>
            </div>
          </fieldset>

          <div className="form-actions">
            <button type="submit" className="button button--primary" disabled={loading || catalogPreview}>
              {catalogPreview ? "Request quote unavailable" : loading ? "Requesting quote…" : "Request quote"}
            </button>
            {error ? <div className="form-error">{error}</div> : null}
          </div>
        </form>

        {summary ? (
          <div className="section">
            <div className="section__header">
              <div>
                <p className="eyebrow">Quote result</p>
                <h2>Estimated landed cost</h2>
              </div>
            </div>
            <div className="quote-summary">
              <div>
                <strong>Total</strong>
                <span>{formatBdt(summary.total_bdt, intlLocale)}</span>
              </div>
              <div>
                <strong>Product cost</strong>
                <span>{formatBdt(summary.product_cost_bdt || summary.origin_price_bdt, intlLocale)}</span>
              </div>
              <div>
                <strong>Shipping</strong>
                <span>{formatBdt(summary.shipping_bdt, intlLocale)}</span>
              </div>
              <div>
                <strong>Customs duty</strong>
                <span>{formatBdt(summary.customs_duty_bdt || summary.duty_vat_bdt, intlLocale)}</span>
              </div>
              <div>
                <strong>VAT / tax</strong>
                <span>{formatBdt(summary.vat_tax_bdt || 0, intlLocale)}</span>
              </div>
              <div>
                <strong>Handling</strong>
                <span>{formatBdt(summary.handling_charge_bdt || summary.service_fee_bdt, intlLocale)}</span>
              </div>
              <div>
                <strong>Advance</strong>
                <span>{formatBdt(summary.advance_bdt, intlLocale)}</span>
              </div>
              <div>
                <strong>Remaining</strong>
                <span>{formatBdt(summary.remaining_bdt, intlLocale)}</span>
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="button button--primary" onClick={handleSave} disabled={savedQuoteId !== null}>{savedQuoteId ? "Saved to comparisons" : "Save for comparison"}</button>
            </div>
            {aiExplanation ? (
              <article className="form-card" aria-labelledby="ai-explanation-title">
                <div className="section__header">
                  <div>
                    <p className="eyebrow">{bn ? "AI-সহায়িত ব্যাখ্যা" : "AI-assisted explanation"}</p>
                    <h2 id="ai-explanation-title">{bn ? "সোর্সিং সিদ্ধান্তের ব্যাখ্যা" : "Sourcing decision explanation"}</h2>
                  </div>
                  <span className={`admin-status admin-status--${aiExplanation.human_review_required ? "pending" : "approved"}`}>
                    {aiExplanation.human_review_required
                      ? (bn ? "মানব পর্যালোচনা প্রয়োজন" : "Human review required")
                      : (bn ? "বাধ্যতামূলক পর্যালোচনা নেই" : "No mandatory review")}
                  </span>
                </div>
                <p>{aiSummary}</p>
                <div className="form-grid">
                  <div><strong>{bn ? "সুবিধা" : "Advantages"}</strong><ul>{aiAdvantages.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div><strong>{bn ? "ঝুঁকি" : "Risks"}</strong><ul>{aiRisks.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div><strong>{bn ? "অনুপস্থিত তথ্য" : "Missing information"}</strong><ul>{aiMissingInformation.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div><strong>{bn ? "যা যাচাই করবেন" : "Recommended checks"}</strong><ul>{aiRecommendedChecks.map((item) => <li key={item}>{item}</li>)}</ul></div>
                </div>
                <small>
                  {aiMetadata?.automation_available
                    ? (bn ? `${aiMetadata.model || "local AI"} দিয়ে তৈরি।` : `Generated with ${aiMetadata.model || "local AI"}.`)
                    : (bn ? "AI সেবা পাওয়া যায়নি; নির্ধারিত fallback দেখানো হয়েছে।" : "AI service unavailable; deterministic fallback shown.")}
                  {aiExplanation.confidence !== null
                    ? (bn ? ` স্ব-প্রতিবেদিত আস্থা: ${Math.round(aiExplanation.confidence * 100)}%।` : ` Self-reported confidence: ${Math.round(aiExplanation.confidence * 100)}%.`)
                    : ""}
                  {bn ? " সব আর্থিক মান সার্ভারে হিসাব করা হয়।" : " All monetary values remain server-calculated."}
                </small>
              </article>
            ) : null}
            {savedQuoteId ? (
              <div className="save-success" role="status">
                <div><strong>Quote saved successfully</strong><span>You can compare it later or continue directly to checkout.</span></div>
                <div className="save-success__actions">
                  <Link className="button button--ghost" href="/account/saved-quotes">View saved comparisons</Link>
                  <Link className="button button--primary" href={`/account/saved-quotes/${savedQuoteId}/order` as Route}>Proceed to order</Link>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </main>
  );
}
