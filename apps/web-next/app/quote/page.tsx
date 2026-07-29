"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { getProducts, getCountries, quoteProduct, saveQuote, type Country, type Product, type QuoteResponse } from "../../lib/api";
import { formatBdt } from "../../lib/format";

export default function QuotePage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null);
  const [form, setForm] = useState({ qty: 1, country: "CN", mode: "LOCAL", delivery_type: "DOOR" });
  const [response, setResponse] = useState<QuoteResponse | null>(null);
  const [savedQuoteId, setSavedQuoteId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedVariant = Number(params.get("variant")) || null;
    const requestedQty = Number(params.get("qty")) || 1;
    const requestedCountry = params.get("country");
    const requestedMode = params.get("mode");
    setForm((prev) => ({ ...prev, qty: requestedQty, country: requestedCountry || prev.country, mode: requestedMode || prev.mode }));
    getProducts().then((items) => {
      setProducts(items);
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

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!selectedVariantId) {
      setError("Select a product variant before requesting a quote.");
      return;
    }
    setLoading(true);
    try {
      const result = await quoteProduct({
        variant_id: selectedVariantId,
        country: form.country,
        mode: form.mode,
        qty: Number(form.qty) || 1,
        delivery_type: form.delivery_type,
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

  return (
    <main className="shell shell--narrow">
      <div className="section">
        <div className="section__header">
          <div>
            <p className="eyebrow">Quote</p>
            <h2>Request a sourcing estimate</h2>
          </div>
        </div>

        <form className="form-card" onSubmit={handleSubmit}>
          <div className="form-grid">
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
                value={form.qty}
                onChange={(event) => setForm((prev) => ({ ...prev, qty: Number(event.target.value) || 1 }))}
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
          </div>

          <div className="form-actions">
            <button type="submit" className="button button--primary" disabled={loading}>
              {loading ? "Requesting quote…" : "Request quote"}
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
                <span>{formatBdt(summary.total_bdt)}</span>
              </div>
              <div>
                <strong>Product cost</strong>
                <span>{formatBdt(summary.product_cost_bdt || summary.origin_price_bdt)}</span>
              </div>
              <div>
                <strong>Shipping</strong>
                <span>{formatBdt(summary.shipping_bdt)}</span>
              </div>
              <div>
                <strong>Customs duty</strong>
                <span>{formatBdt(summary.customs_duty_bdt || summary.duty_vat_bdt)}</span>
              </div>
              <div>
                <strong>VAT / tax</strong>
                <span>{formatBdt(summary.vat_tax_bdt || 0)}</span>
              </div>
              <div>
                <strong>Handling</strong>
                <span>{formatBdt(summary.handling_charge_bdt || summary.service_fee_bdt)}</span>
              </div>
              <div>
                <strong>Advance</strong>
                <span>{formatBdt(summary.advance_bdt)}</span>
              </div>
              <div>
                <strong>Remaining</strong>
                <span>{formatBdt(summary.remaining_bdt)}</span>
              </div>
            </div>
            <div className="form-actions">
              <button type="button" className="button button--primary" onClick={handleSave} disabled={savedQuoteId !== null}>{savedQuoteId ? "Saved to comparisons" : "Save for comparison"}</button>
            </div>
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
