"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useLocale } from "../lib/locale-context";
import { useSourcingBasket } from "../lib/sourcing-basket";
import { localizedCatalogLabel, sourcingText } from "../lib/sourcing-copy";
import { AppIcon } from "./app-icon";

export function QuoteBasketButton({ mobile = false }: { mobile?: boolean }) {
  const { items, itemCount, estimatedProductTotal } = useSourcingBasket();
  const { locale } = useLocale();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const controlRef = useRef<HTMLDivElement>(null);
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!controlRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const hasItems = itemCount > 0;
  const compactLabel = hasItems ? (locale === "bn" ? "বাস্কেট" : "Quote basket") : sourcingText(locale, "getQuote");
  const accessibleLabel = hasItems ? `${sourcingText(locale, "basket")}: ${itemCount}` : sourcingText(locale, "getQuote");
  const icon = hasItems ? "package" : "globe";

  if (mobile) return <Link className="nav-link mobile-account-link" href={(hasItems ? "/sourcing-basket" : "/quote") as Route} aria-label={accessibleLabel}><AppIcon name={icon} size={17} /><span>{compactLabel}</span>{hasItems ? <strong className="basket-count basket-count--inline">{itemCount}</strong> : null}</Link>;

  if (!hasItems) return <div className="quote-basket-control"><Link className="quote-basket-button" href={"/quote" as Route} aria-label={accessibleLabel}><AppIcon name={icon} size={19} /><span className="quote-basket-button__label">{compactLabel}</span></Link></div>;

  return <div className="quote-basket-control" ref={controlRef}>
    <button className="quote-basket-button" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-haspopup="dialog" aria-controls="quote-basket-preview" aria-label={accessibleLabel}>
      <AppIcon name={icon} size={19} /><span className="quote-basket-button__label">{compactLabel}</span><strong className="basket-count">{itemCount}</strong>
    </button>
    {open ? <div className="quote-basket-preview" id="quote-basket-preview" role="dialog" aria-label={sourcingText(locale, "basket")}>
      <div className="quote-basket-preview__header"><strong>{sourcingText(locale, "basket")}</strong><button type="button" onClick={() => setOpen(false)} aria-label={locale === "bn" ? "বাস্কেট প্রিভিউ বন্ধ করুন" : "Close basket preview"}>×</button></div>
      {items.length ? <><div className="quote-basket-preview__items">{items.slice(0, 3).map((item) => <Link className="quote-basket-preview__item" href={`/products/${item.productSlug}` as Route} onClick={() => setOpen(false)} key={item.key} aria-label={`${sourcingText(locale, "viewProduct")}: ${item.productName}`}><span><strong>{item.productName}</strong><small>{localizedCatalogLabel(locale, item.variantName)} · {item.countryCode}</small></span><span className="quote-basket-preview__item-end"><b>×{new Intl.NumberFormat(locale === "bn" ? "bn-BD" : "en-US").format(item.quantity)}</b><i aria-hidden="true">→</i></span></Link>)}{items.length > 3 ? <small className="quote-basket-preview__more">+{new Intl.NumberFormat(locale === "bn" ? "bn-BD" : "en-US").format(items.length - 3)} {locale === "bn" ? "টি আরও পণ্য" : "more items"}</small> : null}</div>
        <div className="quote-basket-preview__total"><span>{sourcingText(locale, "estimatedProductCost")}</span><strong>{new Intl.NumberFormat(locale === "bn" ? "bn-BD" : "en-US", { style: "currency", currency: "USD" }).format(estimatedProductTotal)}</strong></div>
        <Link className="button button--primary" href={"/sourcing-basket" as Route} onClick={() => setOpen(false)}>{sourcingText(locale, "viewBasket")}</Link></> : <div className="quote-basket-preview__empty"><AppIcon name="package" size={28} /><span>{sourcingText(locale, "basketEmpty")}</span></div>}
    </div> : null}
  </div>;
}
