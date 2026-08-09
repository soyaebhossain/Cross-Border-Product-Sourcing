"use client";

import Link from "next/link";
import { useState } from "react";
import { ProductImage } from "../../components/product-image";
import { QuantitySelector, RiskBadge } from "../../components/sourcing-ui";
import { quoteProductWithAi, saveQuote } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";
import { useSourcingBasket } from "../../lib/sourcing-basket";
import { localizedCatalogLabel, sourcingText } from "../../lib/sourcing-copy";

function money(amount: number, currency: string, locale: "en" | "bn") {
  return new Intl.NumberFormat(locale === "bn" ? "bn-BD" : "en-US", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
}

export default function SourcingBasketPage() {
  const { items, itemCount, estimatedProductTotal, removeItem, updateItem } = useSourcingBasket();
  const { locale } = useLocale();
  const [requesting, setRequesting] = useState(false);
  const [result, setResult] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const requestQuotes = async () => {
    if (!items.length) return;
    setRequesting(true);
    setResult(null);
    let saved = 0;
    try {
      for (const item of items) {
        const response = await quoteProductWithAi({ variant_id: item.variantId, country: item.countryCode, mode: "LOCAL", qty: item.quantity, delivery_type: "DOOR", language: locale });
        await saveQuote({ variant_id: item.variantId, country: item.countryCode, mode: "LOCAL", qty: item.quantity, delivery_type: "DOOR", response });
        saved += 1;
      }
      setResult({ type: "success", message: locale === "bn" ? `${saved}টি কোট সফলভাবে তৈরি ও সংরক্ষণ হয়েছে।` : `${saved} quote${saved === 1 ? "" : "s"} created and saved successfully.` });
    } catch {
      setResult({ type: "error", message: saved ? (locale === "bn" ? `${saved}টি কোট সংরক্ষণ হয়েছে; বাকি কোটগুলো সম্পন্ন হয়নি। আবার চেষ্টা করুন।` : `${saved} quote${saved === 1 ? "" : "s"} saved; the remaining requests could not be completed. Please try again.`) : (locale === "bn" ? "কোট service এখন পাওয়া যাচ্ছে না অথবা কোট সংরক্ষণ করতে sign in প্রয়োজন। আপনার বাস্কেট সংরক্ষিত আছে।" : "The quote service is unavailable or sign-in is required to save quotes. Your basket is still saved.") });
    } finally {
      setRequesting(false);
    }
  };

  if (!items.length) return <main className="sourcing-basket-page"><section className="basket-empty-state"><h1>{sourcingText(locale, "basketEmpty")}</h1><p>{sourcingText(locale, "basketEmptyHelp")}</p><Link className="button button--primary" href="/products">{sourcingText(locale, "continueSourcing")}</Link></section></main>;

  return <main className="sourcing-basket-page">
    <header className="basket-page-heading"><div><span className="market-kicker">{locale === "bn" ? "কোট-ভিত্তিক সোর্সিং" : "Quote-based sourcing"}</span><h1>{sourcingText(locale, "basket")}</h1><p>{locale === "bn" ? "ভ্যারিয়েন্ট, উৎস ও পরিমাণ নিশ্চিত করুন। সাপ্লায়ার, শিপিং ও কাস্টমস যাচাইয়ের পর চূড়ান্ত কোট দেওয়া হবে।" : "Confirm variant, origin, and quantity. The final quotation follows supplier, shipping, and customs verification."}</p></div><Link className="button button--ghost" href="/products">{sourcingText(locale, "continueSourcing")}</Link></header>
    <div className="basket-layout">
      <section className="basket-items" aria-label={sourcingText(locale, "basket")}>
        {items.map((item) => {
          const subtotal = (item.estimatedUnitPrice || 0) * item.quantity;
          return <article className="basket-item" key={item.key}>
            <Link className="basket-item__media" href={`/products/${item.productSlug}`} aria-label={`${sourcingText(locale, "viewProduct")}: ${item.productName}`}><ProductImage src={item.imageSrc} name={item.productName} category={item.categoryName} alt={item.imageAlt} showLabel={false} sizes="126px" /></Link>
            <div className="basket-item__body">
              <div className="basket-item__title"><div><span className="eyebrow">{localizedCatalogLabel(locale, item.categoryName)}</span><h2><Link href={`/products/${item.productSlug}`}>{item.productName}</Link></h2></div><button type="button" className="basket-item__remove" onClick={() => removeItem(item.key)} aria-label={`${sourcingText(locale, "remove")}: ${item.productName}`}>{sourcingText(locale, "remove")}</button></div>
              <div className="basket-item__controls">
                <label>{sourcingText(locale, "variant")}<select value={item.variantId} onChange={(event) => { const variantId = Number(event.target.value); const variant = item.variants.find((row) => row.id === variantId); updateItem(item.key, { variantId, variantName: variant?.variant_name || variant?.sku || `Variant ${variantId}` }); }}>{item.variants.map((variant) => <option key={variant.id} value={variant.id}>{localizedCatalogLabel(locale, variant.variant_name || variant.sku || `Variant ${variant.id}`)}</option>)}</select></label>
                <label>{sourcingText(locale, "origin")}<select value={item.countryCode} onChange={(event) => updateItem(item.key, { countryCode: event.target.value })}>{item.availableCountries.map((code) => <option key={code} value={code}>{code}</option>)}</select></label>
                <div className="basket-item__control"><span>{sourcingText(locale, "quantity")}</span><QuantitySelector value={item.quantity} min={item.moq} onChange={(quantity) => updateItem(item.key, { quantity })} label={`${sourcingText(locale, "quantity")}: ${item.productName}`} /></div>
              </div>
              <div className="basket-item__meta"><span>{sourcingText(locale, "moq")}: {sourcingText(locale, "confirmSupplier")}</span><span>{item.deliveryMinDays ? `${item.deliveryMinDays}–${item.deliveryMinDays + 7} ${locale === "bn" ? "দিন" : "days"}` : sourcingText(locale, "confirmSupplier")}</span><span>{sourcingText(locale, "supplierPending")}</span><RiskBadge level={item.riskLevel} /></div>
              <div className="basket-item__price"><span><small>{sourcingText(locale, "estimatedUnitPrice")}</small><strong>{item.estimatedUnitPrice === null ? (locale === "bn" ? "কোটে জানানো হবে" : "On request") : money(item.estimatedUnitPrice, item.currency, locale)}</strong></span><span><small>{sourcingText(locale, "estimatedSubtotal")}</small><strong>{item.estimatedUnitPrice === null ? "—" : money(subtotal, item.currency, locale)}</strong></span></div>
              <p className="pricing-disclaimer">{sourcingText(locale, "landedCostPending")} · {sourcingText(locale, "shippingDisclaimer")}</p>
            </div>
          </article>;
        })}
      </section>
      <aside className="basket-summary"><h2>{locale === "bn" ? "অনুরোধের সারাংশ" : "Request summary"}</h2><div className="basket-summary__row"><span>{locale === "bn" ? "পণ্যের সংখ্যা" : "Basket items"}</span><strong>{new Intl.NumberFormat(locale === "bn" ? "bn-BD" : "en-US").format(itemCount)}</strong></div><div className="basket-summary__row basket-summary__row--total"><span>{sourcingText(locale, "estimatedProductCost")}</span><strong>{money(estimatedProductTotal, "USD", locale)}</strong></div><p className="pricing-disclaimer">{sourcingText(locale, "shippingDisclaimer")}</p><p className="pricing-disclaimer">{sourcingText(locale, "finalQuoteDisclaimer")}</p><button type="button" className="button button--primary" onClick={requestQuotes} disabled={requesting}>{requesting ? (locale === "bn" ? "কোট তৈরি হচ্ছে…" : "Creating quotes…") : sourcingText(locale, itemCount === 1 ? "requestQuote" : "requestQuotes")}</button>{result ? <div className={`basket-summary__message${result.type === "error" ? " basket-summary__message--error" : ""}`} role="status">{result.message}{result.type === "success" ? <><br /><Link href="/account/saved-quotes">{locale === "bn" ? "সংরক্ষিত কোট দেখুন" : "View saved quotes"}</Link></> : null}</div> : null}</aside>
    </div>
  </main>;
}
