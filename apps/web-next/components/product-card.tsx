"use client";

import Link from "next/link";
import type { Product } from "../lib/api";
import { getProductMedia } from "../lib/api";
import { useLocale } from "../lib/locale-context";
import { useSourcingBasket } from "../lib/sourcing-basket";
import { localizedCatalogLabel, sourcingText } from "../lib/sourcing-copy";
import { ProductImage } from "./product-image";
import { PriceDisplay, RiskBadge, TrustBadge } from "./sourcing-ui";

type ProductCardProps = {
  product: Product;
  imagePriority?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: number) => void;
};

export function ProductCard({ product, imagePriority, selectable, selected, onSelect }: ProductCardProps) {
  const media = getProductMedia(product)[0];
  const market = product.market;
  const { addProduct } = useSourcingBasket();
  const { locale } = useLocale();
  const origin = market?.countries?.[0];
  const eta = market?.min_delivery_days;
  const hasVariant = product.variants.length > 0;

  return <article className="product-card">
    {selectable ? <label className="compare-check"><input type="checkbox" checked={selected} onChange={() => onSelect?.(product.id)} /> {locale === "bn" ? "তুলনা" : "Compare"}</label> : null}
    <div className="product-card__visual">
      <Link className="product-card__media-link" href={`/products/${product.slug}`} aria-label={`${sourcingText(locale, "viewProduct")}: ${product.name}`}>
        <ProductImage src={media.src} name={product.name} category={product.category.name} alt={media.alt} sourceKind={media.kind} verified={media.verified} priority={imagePriority} />
      </Link>
    </div>
    <div className="product-card__copy">
      <div className="card-signals">
        <TrustBadge explanation={locale === "bn" ? "ব্যাখ্যাযোগ্য, AI-assisted decision support; চূড়ান্ত সিদ্ধান্ত নয়।" : "Explainable AI-assisted decision support, not a final decision."}>{locale === "bn" ? "AI সহায়তাপ্রাপ্ত" : "AI assisted"}</TrustBadge>
        <TrustBadge explanation={locale === "bn" ? "উপলভ্য পণ্য ও সাপ্লায়ার তথ্য ব্যবহার করে ঝুঁকি যাচাই করা হয়েছে।" : "Risk checked using available product and supplier data."}>{sourcingText(locale, "riskChecked")}</TrustBadge>
      </div>
      <p className="eyebrow">{localizedCatalogLabel(locale, product.category.name)}</p>
      <h3><Link className="product-card__title-link" href={`/products/${product.slug}`}>{product.name}</Link></h3>
      <p className="meta">{product.model || (locale === "bn" ? "মডেল উল্লেখ নেই" : "Model not specified")}</p>
      <div className="product-card__price-row"><PriceDisplay amount={market?.min_price} currency={market?.currency} /><RiskBadge level={market?.risk_level} /></div>
      <dl className="product-card__facts">
        <div><dt>{sourcingText(locale, "origin")}</dt><dd>{origin || sourcingText(locale, "confirmSupplier")}</dd></div>
        <div><dt>{locale === "bn" ? "ডেলিভারি" : "Delivery"}</dt><dd>{eta ? `${eta}–${eta + 7} ${locale === "bn" ? "দিন" : "days"}` : sourcingText(locale, "confirmSupplier")}</dd></div>
        <div><dt>{sourcingText(locale, "moq")}</dt><dd>{sourcingText(locale, "confirmSupplier")}</dd></div>
        <div><dt>{locale === "bn" ? "রেটিং" : "Rating"}</dt><dd>{market?.max_rating ? `★ ${market.max_rating.toFixed(1)}` : "—"}</dd></div>
      </dl>
      <p className="pricing-disclaimer">{sourcingText(locale, "shippingDisclaimer")}</p>
      <div className="product-card__footer">
        <span className="product-card__variant-count">{product.variants.length} {locale === "bn" ? "ভ্যারিয়েন্ট" : `variant${product.variants.length === 1 ? "" : "s"}`}</span>
        <div className="product-card__actions">
          <Link className="button card-action card-action--secondary" href={`/products/${product.slug}`}>{sourcingText(locale, "viewProduct")}</Link>
          <button className="button card-action card-action--primary" type="button" disabled={!hasVariant} onClick={() => addProduct(product)}>{sourcingText(locale, "addToQuote")}</button>
        </div>
      </div>
    </div>
  </article>;
}
