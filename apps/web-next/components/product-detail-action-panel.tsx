"use client";

import Link from "next/link";
import type { Route } from "next";
import { useMemo, useState } from "react";
import type { Product } from "../lib/api";
import { useLocale } from "../lib/locale-context";
import { useSourcingBasket } from "../lib/sourcing-basket";
import { sourcingText } from "../lib/sourcing-copy";
import { PriceDisplay, QuantitySelector, RiskBadge, TrustBadge } from "./sourcing-ui";
import { useProductQuantity } from "./product-quantity";
import { OrderSteps } from "./order-steps";

export function ProductDetailActionPanel({ product, landedCostAvailable = false }: { product: Product; landedCostAvailable?: boolean }) {
  const defaultVariant = product.variants.find((item) => item.id === product.default_variant_id) || product.variants[0];
  const [variantId, setVariantId] = useState(defaultVariant?.id || 0);
  const { quantity, setQuantity } = useProductQuantity();
  const countries = product.market?.countries?.length ? product.market.countries : ["CN"];
  const [countryCode, setCountryCode] = useState(countries[0]);
  const { addProduct } = useSourcingBasket();
  const { locale } = useLocale();
  const quoteHref = useMemo(() => `/quote?variant=${variantId}&qty=${quantity}&country=${countryCode}&auto=1` as Route, [variantId, quantity, countryCode]);
  if (!defaultVariant) return null;
  const market = product.market;
  const eta = market?.min_delivery_days;
  return <aside className="product-action-panel" aria-labelledby="product-action-title">
    <OrderSteps current={1} />
    <div className="product-action-panel__heading"><div><span>{sourcingText(locale, "estimatedUnitPrice")}</span><PriceDisplay amount={product.market?.min_price} currency={product.market?.currency} /></div><RiskBadge level={product.market?.risk_level} /></div>
    <h2 id="product-action-title">{locale === "bn" ? "আপনার সোর্সিং অনুরোধ তৈরি করুন" : "Build your sourcing request"}</h2>
    <div className="product-action-panel__fields">
      <label>{sourcingText(locale, "variant")}<select value={variantId} onChange={(event) => setVariantId(Number(event.target.value))}>{product.variants.map((variant) => <option key={variant.id} value={variant.id}>{variant.variant_name || variant.sku || `Variant ${variant.id}`}</option>)}</select></label>
      <label>{sourcingText(locale, "origin")}<select value={countryCode} onChange={(event) => setCountryCode(event.target.value)}>{countries.map((code) => <option key={code} value={code}>{code}</option>)}</select></label>
      <div className="product-action-panel__quantity"><span>{sourcingText(locale, "quantity")}</span><QuantitySelector value={quantity} min={1} onChange={setQuantity} label={sourcingText(locale, "quantity")} /></div>
    </div>
    <div className="product-action-panel__facts"><span><small>{sourcingText(locale, "moq")}</small><strong>{market?.min_moq ? (locale === "bn" ? `${market.min_moq} টি থেকে` : `From ${market.min_moq} ${market.min_moq === 1 ? "unit" : "units"}`) : sourcingText(locale, "confirmSupplier")}</strong></span><span><small>{locale === "bn" ? "আনুমানিক ডেলিভারি" : "Estimated delivery"}</small><strong>{eta ? (market?.max_delivery_days ? `${eta}–${market.max_delivery_days} ${locale === "bn" ? "দিন" : "days"}` : `${eta}+ ${locale === "bn" ? "দিন" : "days"}`) : sourcingText(locale, "confirmSupplier")}</strong></span></div>
    <div className="product-action-panel__actions"><Link className="button button--primary" href={quoteHref}>{locale === "bn" ? "এখনই অর্ডার করুন" : "Order now"}</Link><button type="button" className="button button--ghost" onClick={() => addProduct(product, { variantId, quantity, countryCode })}>{sourcingText(locale, "addToQuote")}</button></div>
    <p className="product-action-panel__next">{locale === "bn" ? "“এখনই অর্ডার করুন” চাপলে শিপিং, শুল্ক ও VAT সহ মোট খরচ দেখাবে; তারপর এক ধাপে অর্ডার নিশ্চিত করা যাবে। একাধিক পণ্য একসাথে নিতে “কোটে যোগ করুন” ব্যবহার করুন।" : "“Order now” shows the full cost with shipping, duty and VAT, then lets you confirm the order in one step. Use “Add to quote” to collect several products first."}</p>
    <div className="product-action-panel__trust"><TrustBadge explanation={locale === "bn" ? "উপলভ্য পণ্য ও সাপ্লায়ার তথ্য ব্যবহার করে ঝুঁকি যাচাই করা হয়েছে।" : "Risk is checked using available product and supplier data."}>{sourcingText(locale, "riskChecked")}</TrustBadge>{landedCostAvailable ? null : <TrustBadge explanation={locale === "bn" ? "চূড়ান্ত মূল্য শিপিং, ট্যারিফ ও কাস্টমস যাচাইয়ের পর নিশ্চিত হবে।" : "Final price is confirmed after shipping, tariff, and customs checks."}>{sourcingText(locale, "landedCostPending")}</TrustBadge>}</div>
    <p className="pricing-disclaimer">{sourcingText(locale, "shippingDisclaimer")} {sourcingText(locale, "finalQuoteDisclaimer")}</p>
  </aside>;
}
