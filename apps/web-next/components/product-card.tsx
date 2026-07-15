import Link from "next/link";
import type { Product } from "../lib/api";
import { resolveImageUrl } from "../lib/api";
import { ProductImage } from "./product-image";

type ProductCardProps = {
  product: Product;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: number) => void;
};

function CheckIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden><path d="m5 10 3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function ProductCard({ product, selectable, selected, onSelect }: ProductCardProps) {
  const image = resolveImageUrl(product.image);
  const market = product.market;

  return <article className="product-card">
    {selectable ? <label className="compare-check"><input type="checkbox" checked={selected} onChange={() => onSelect?.(product.id)} /> Compare</label> : null}
    <div className="product-card__copy">
      <div className="card-signals"><span><CheckIcon /> AI assessed</span><span><CheckIcon /> Risk checked</span></div>
      <p className="eyebrow">{product.category.name}</p>
      <h3>{product.name}</h3>
      <p className="meta">{product.model || "Model not specified"}</p>
      {market ? <div className="market-signals">
        <span>{market.min_price ?? "—"} {market.currency || "USD"}</span>
        <span aria-label="Supplier rating">★ {market.max_rating?.toFixed(1) || "—"}</span>
        <span>{market.min_delivery_days || "—"} days</span>
        <span className={`risk-text risk-text--${market.risk_level?.toLowerCase()}`}>{market.risk_level} risk</span>
      </div> : null}
      <p className="summary">{product.description || "Supplier offer ready for landed-cost and risk comparison."}</p>
      <div className="meta-row"><span>{product.variants.length} variant{product.variants.length === 1 ? "" : "s"}</span><Link className="card-action" href={`/products/${product.slug}`}>Compare sourcing <span aria-hidden>→</span></Link></div>
    </div>
    <div className="product-card__visual"><ProductImage src={image} name={product.name} category={product.category.name} /></div>
  </article>;
}
