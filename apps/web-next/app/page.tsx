import Link from "next/link";
import { AppIcon } from "../components/app-icon";
import { CategoryIcon } from "../components/category-icon";
import { ProductCard } from "../components/product-card";
import { browseProducts, getCategories, getSourcingLanes } from "../lib/api";

export default async function HomePage() {
  const [catalog, categories, allLanes] = await Promise.all([
    browseProducts({ pageSize: 60 }).catch(() => null),
    getCategories().catch(() => []),
    getSourcingLanes().catch(() => []),
  ]);
  const popularProducts = (() => {
    if (!catalog) return [];
    const selected = [];
    const selectedIds = new Set<number>();
    const representedCategories = new Set<string>();

    for (const product of catalog.items) {
      if (!product.image || representedCategories.has(product.category.slug)) continue;
      selected.push(product);
      selectedIds.add(product.id);
      representedCategories.add(product.category.slug);
      if (selected.length === 8) return selected;
    }
    // Keep the remaining slots photo-backed whenever possible. The first pass
    // maximizes category diversity; this pass reuses categories before falling
    // back to an illustrative card only when the result set has fewer than
    // eight products with assigned media.
    for (const product of catalog.items) {
      if (!product.image || selectedIds.has(product.id)) continue;
      selected.push(product);
      selectedIds.add(product.id);
      if (selected.length === 8) return selected;
    }
    for (const product of catalog.items) {
      if (selectedIds.has(product.id)) continue;
      selected.push(product);
      selectedIds.add(product.id);
      if (selected.length === 8) break;
    }
    return selected;
  })();
  const featuredCategorySlugs = [
    "mobile-accessories",
    "laptop-pc-accessories",
    "educational-academic-tools",
    "creator-content-tools",
    "ecommerce-packaging-supplies",
    "home-organization-storage",
    "fashion-accessories",
    "beauty-tools-accessories",
    "kitchen-utility-tools",
    "office-desk-accessories",
    "jewelry-gems-precious-metals",
    "medical-products-accessories",
  ];
  const priorityCategories = featuredCategorySlugs.flatMap((slug) => {
    const category = categories.find((item) => item.slug === slug);
    return category ? [category] : [];
  });
  const featuredCategories = priorityCategories;

  // Lanes come from the live catalog: only origins with active offers, with their configured ETA.
  const lanes = allLanes.slice(0, 4).map((lane) => ({
    code: lane.code,
    name: `${lane.name} → Bangladesh`,
    eta: lane.eta_min_days && lane.eta_max_days ? `${lane.eta_min_days}–${lane.eta_max_days} days by air` : "ETA on request",
    badge: `${lane.products} products`,
  }));
  const otherOrigins = allLanes.slice(4).map((lane) => lane.name);

  return (
    <main className="market-shell">
      {catalog?.catalog_source === "snapshot" ? (
        <div className="catalog-preview-notice" role="status">
          <strong>Catalog preview</strong>
          <span>Products are available to browse. Live quotes and ordering are temporarily unavailable.</span>
        </div>
      ) : null}
      <section className="market-hero">
        <div className="hero-copy">
          <span className="hero-pill">AI-assisted cross-border sourcing</span>
          <h1>Make every global sourcing decision with confidence.</h1>
          <p>Compare landed cost, supplier reliability, delivery time and sourcing risk—then choose the best route for your business.</p>
          <form action="/products" className="hero-search">
            <input name="q" placeholder="What product are you sourcing?" />
            <button>Search marketplace</button>
          </form>
          <div className="hero-trust"><span><AppIcon name="check" size={15} />{catalog ? `${catalog.total} products` : "Global product catalog"}</span><span><AppIcon name="check" size={15} />Explainable ranking</span><span><AppIcon name="check" size={15} />Landed-cost clarity</span></div>
        </div>
        <div className="lane-board-new">
          <div className="lane-title"><span>Featured sourcing lanes</span><strong>Decision snapshot</strong></div>
          {lanes.map((lane) => <div className="lane-item" key={lane.code}><b>{lane.code}</b><div><strong>{lane.name}</strong><span>{lane.eta}</span></div><em>{lane.badge}</em></div>)}
          <p>{otherOrigins.length ? `Catalog origins also include ${otherOrigins.join(", ")}. ` : ""}{lanes.length ? "Scores combine cost, quality, reliability, delivery and risk." : "Live lane data is temporarily unavailable."}</p>
        </div>
      </section>

      <section className="market-section">
        <div className="market-section-title">
          <div><span className="market-kicker">Browse by category</span><h2>Explore sourcing opportunities</h2></div>
          <Link href="/products">View all categories →</Link>
        </div>
        <div className="category-strip">
          {featuredCategories.map((category) => (
            <Link key={category.id} href={`/products?category=${category.slug}`}>
              <CategoryIcon name={category.name} />
              <strong>{category.name}</strong>
            </Link>
          ))}
        </div>
      </section>

      <section className="market-section">
        <div className="market-section-title">
          <div><span className="market-kicker">Live catalog</span><h2>Popular products</h2></div>
          <Link href="/products">{catalog ? `Browse all ${catalog.total}` : "Browse catalog"} →</Link>
        </div>
        {popularProducts.length ? <div className="compact-grid">{popularProducts.map((product, index) => <ProductCard key={product.id} product={product} imagePriority={index < 4} />)}</div> : <div className="market-empty">Catalog is starting. Please refresh shortly.</div>}
      </section>

      <section className="decision-banner">
        <div><span className="market-kicker">Built for better decisions</span><h2>More than a marketplace.</h2><p>Adjust your priorities and get an explainable supplier and country recommendation.</p></div>
        <Link href="/products">Start sourcing →</Link>
      </section>
    </main>
  );
}
