import Link from "next/link";
import { ProductComparison } from "../../components/product-comparison";
import { getProducts } from "../../lib/api";

type ComparePageProps = { searchParams: Promise<{ products?: string }> };

export default async function ComparePage({ searchParams }: ComparePageProps) {
  const { products: rawIds } = await searchParams;
  const ids = Array.from(new Set(
    (rawIds || "")
      .split(",")
      .map(Number)
      .filter((id) => Number.isSafeInteger(id) && id > 0),
  )).slice(0, 4);
  const catalog = await getProducts().catch(() => []);
  const selected = ids.flatMap((id) => { const product = catalog.find((item) => item.id === id); return product ? [product] : []; });
  return <main className="comparison-page"><Link href="/products" className="back-link">← Back to catalog</Link><header className="basket-page-heading"><div><span className="market-kicker">Explainable sourcing comparison</span><h1>Compare products</h1><p>Review product price, origin, delivery, risk, and data gaps before adding products to your sourcing basket.</p></div></header><ProductComparison products={selected} /></main>;
}
