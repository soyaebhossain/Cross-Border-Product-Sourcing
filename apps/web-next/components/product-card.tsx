import Link from "next/link";
import type { Product } from "../lib/api";
import { getProductMedia } from "../lib/api";
import { formatAmount } from "../lib/format";
import { ProductImage } from "./product-image";

type ProductCardProps = {
  product: Product;
  imagePriority?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: number) => void;
};

function CheckIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden><path d="m5 10 3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function ProductCard({ product, imagePriority, selectable, selected, onSelect }: ProductCardProps) {
  const media = getProductMedia(product)[0];
  const market = product.market;
  const hasIndicativePreciousPricing =
    product.category.slug === "jewelry-gems-precious-metals";

  return <article className="product-card">
    {selectable ? <label className="compare-check"><input type="checkbox" checked={selected} onChange={() => onSelect?.(product.id)} /> Compare</label> : null}
    <div className="product-card__visual">
      <Link className="product-card__media-link" href={`/products/${product.slug}`} aria-label={`View ${product.name}`}>
        <ProductImage
          src={media.src}
          name={product.name}
          category={product.category.name}
          alt={media.alt}
          sourceKind={media.kind}
          verified={media.verified}
          priority={imagePriority}
        />
      </Link>
    </div>
    <div className="product-card__copy">
      <div className="card-signals"><span><CheckIcon /> AI assessed</span><span><CheckIcon /> Risk checked</span></div>
      <p className="eyebrow">{product.category.name}</p>
      <h3>{product.name}</h3>
      <p className="meta">{product.model || "Model not specified"}</p>
      {market ? <div className="market-signals">
        <span>{hasIndicativePreciousPricing ? "Indicative " : ""}{formatAmount(market.min_price)} {market.currency || "USD"}</span>
        <span aria-label="Supplier rating">★ {market.max_rating?.toFixed(1) || "—"}</span>
        <span>{market.min_delivery_days || "—"} days</span>
        <span className={`risk-text risk-text--${market.risk_level?.toLowerCase()}`}>{market.risk_level} risk</span>
      </div> : null}
      <p className="summary">{product.description || "Supplier offer ready for landed-cost and risk comparison."}</p>
      <div className="meta-row"><span>{product.variants.length} variant{product.variants.length === 1 ? "" : "s"}</span><Link className="card-action" href={`/products/${product.slug}`}>{product.catalog_source === "snapshot" ? "View product" : "Compare sourcing"} <span aria-hidden>→</span></Link></div>
    </div>
  </article>;
}
