"use client";

import Link from "next/link";
import type { Product } from "../lib/api";
import { useLocale } from "../lib/locale-context";
import { useSourcingBasket } from "../lib/sourcing-basket";
import { sourcingText } from "../lib/sourcing-copy";
import { PriceDisplay, RiskBadge } from "./sourcing-ui";

export function ProductComparison({ products }: { products: Product[] }) {
  const { addProduct } = useSourcingBasket();
  const { locale } = useLocale();
  if (!products.length) return <section className="basket-empty-state"><h2>{locale === "bn" ? "তুলনার জন্য কোনো পণ্য নেই" : "No products selected for comparison"}</h2><p>{locale === "bn" ? "ক্যাটালগ থেকে ২–৪টি পণ্য বেছে নিন।" : "Choose 2–4 products from the catalog to compare sourcing signals."}</p><Link className="button button--primary" href="/products">{sourcingText(locale, "continueSourcing")}</Link></section>;

  const rows: Array<{ label: string; value: (product: Product) => React.ReactNode }> = [
    { label: locale === "bn" ? "আনুমানিক মূল্য" : "Estimated price", value: (product) => <PriceDisplay amount={product.market?.min_price} currency={product.market?.currency} compact /> },
    { label: sourcingText(locale, "moq"), value: () => sourcingText(locale, "confirmSupplier") },
    { label: sourcingText(locale, "origin"), value: (product) => product.market?.countries?.join(", ") || sourcingText(locale, "confirmSupplier") },
    { label: locale === "bn" ? "সাপ্লায়ার" : "Supplier", value: (product) => product.market?.supplier_count ? `${product.market.supplier_count} ${locale === "bn" ? "টি offer" : "offers"}` : sourcingText(locale, "supplierPending") },
    { label: "ETA", value: (product) => product.market?.min_delivery_days ? `${product.market.min_delivery_days}–${product.market.min_delivery_days + 7} ${locale === "bn" ? "দিন" : "days"}` : "—" },
    { label: locale === "bn" ? "ঝুঁকি" : "Risk", value: (product) => <RiskBadge level={product.market?.risk_level} /> },
    { label: locale === "bn" ? "ল্যান্ডেড কস্ট" : "Landed cost", value: () => sourcingText(locale, "landedCostPending") },
    { label: locale === "bn" ? "রেটিং" : "Rating", value: (product) => product.market?.max_rating ? `★ ${product.market.max_rating.toFixed(1)}` : "—" },
    { label: locale === "bn" ? "মূল স্পেসিফিকেশন" : "Key specs", value: (product) => { const variant = product.variants[0]; return variant ? `${variant.variant_name || variant.sku || "Standard"} · ${variant.weight_kg} kg` : "—"; } },
    { label: locale === "bn" ? "উপযুক্ত" : "Best for", value: (product) => product.market?.risk_level === "Low" ? (locale === "bn" ? "কম ঝুঁকির sourcing shortlist" : "Lower-risk sourcing shortlist") : (locale === "bn" ? "কোট ও supplier verification" : "Quote and supplier verification") },
  ];

  return <div className="comparison-scroll"><table className="comparison-table"><thead><tr><th>{locale === "bn" ? "তুলনার বিষয়" : "Compare"}</th>{products.map((product) => <th key={product.id}><div className="comparison-table__product"><strong>{product.name}</strong><small>{product.model || product.category.name}</small><button type="button" className="button button--primary" onClick={() => addProduct(product)}>{sourcingText(locale, "addToQuote")}</button><Link href={`/products/${product.slug}`}>{sourcingText(locale, "viewProduct")}</Link></div></th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th>{products.map((product) => <td key={product.id}>{row.value(product)}</td>)}</tr>)}</tbody></table></div>;
}
