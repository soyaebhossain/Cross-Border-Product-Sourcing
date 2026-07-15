import Link from "next/link";
import { ProductCard } from "../components/product-card";
import { browseProducts, getCategories } from "../lib/api";

export default async function HomePage() {
  const [catalog, categories] = await Promise.all([browseProducts({ pageSize: 8 }).catch(() => null), getCategories().catch(() => [])]);
  return <main className="market-shell">
    <section className="market-hero"><div className="hero-copy"><span className="hero-pill">AI-assisted cross-border sourcing</span><h1>Make every global sourcing decision with confidence.</h1><p>Compare landed cost, supplier reliability, delivery time and sourcing risk—then choose the best route for your business.</p><form action="/products" className="hero-search"><input name="q" placeholder="What product are you sourcing?"/><button>Search marketplace</button></form><div className="hero-trust"><span>✓ 350 products</span><span>✓ Explainable ranking</span><span>✓ Landed-cost clarity</span></div></div>
      <div className="lane-board-new"><div className="lane-title"><span>Live sourcing lanes</span><strong>Decision snapshot</strong></div>{[{c:"CN",n:"China → Bangladesh",e:"7–14 days",b:"Best value"},{c:"SG",n:"Singapore → Bangladesh",e:"4–8 days",b:"Fastest"},{c:"TH",n:"Thailand → Bangladesh",e:"6–12 days",b:"Low risk"}].map(l=><div className="lane-item" key={l.c}><b>{l.c}</b><div><strong>{l.n}</strong><span>{l.e}</span></div><em>{l.b}</em></div>)}<p>Scores combine cost, quality, reliability, delivery and risk.</p></div>
    </section>
    <section className="market-section"><div className="market-section-title"><div><span className="market-kicker">Browse by category</span><h2>Explore sourcing opportunities</h2></div><Link href="/products">View all categories →</Link></div><div className="category-strip">{categories.slice(0,8).map(c=><Link key={c.id} href={`/products?category=${c.slug}`}><span>{c.name.slice(0,1)}</span><strong>{c.name}</strong></Link>)}</div></section>
    <section className="market-section"><div className="market-section-title"><div><span className="market-kicker">Live catalog</span><h2>Popular products</h2></div><Link href="/products">Browse all {catalog?.total || 350} →</Link></div>{catalog?.items.length ? <div className="compact-grid">{catalog.items.map(p=><ProductCard key={p.id} product={p}/>)}</div> : <div className="market-empty">Catalog is starting. Please refresh shortly.</div>}</section>
    <section className="decision-banner"><div><span className="market-kicker">Built for better decisions</span><h2>More than a marketplace.</h2><p>Adjust your priorities and get an explainable supplier and country recommendation.</p></div><Link href="/products">Start sourcing →</Link></section>
  </main>;
}
