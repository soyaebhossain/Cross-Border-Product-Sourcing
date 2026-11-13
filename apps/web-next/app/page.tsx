import Link from "next/link";
import { AppIcon } from "../components/app-icon";
import { CategoryIcon } from "../components/category-icon";
import { ProductCard } from "../components/product-card";
import { browseProducts, getCategories, getSourcingLanes } from "../lib/api";
import { countryName, getServerLocale } from "../lib/server-locale";

export default async function HomePage() {
  const locale = await getServerLocale();
  const bn = locale === "bn";
  const count = (value: number) => (bn ? new Intl.NumberFormat("bn-BD").format(value) : String(value));
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
    name: bn ? `${countryName(lane.code, lane.name, locale)} → বাংলাদেশ` : `${lane.name} → Bangladesh`,
    eta: lane.eta_min_days && lane.eta_max_days
      ? (bn ? `আকাশপথে ${count(lane.eta_min_days)}–${count(lane.eta_max_days)} দিন` : `${lane.eta_min_days}–${lane.eta_max_days} days by air`)
      : (bn ? "সময় জানতে যোগাযোগ করুন" : "ETA on request"),
    badge: bn ? `${count(lane.products)}টি পণ্য` : `${lane.products} products`,
  }));
  const otherOrigins = allLanes.slice(4).map((lane) => countryName(lane.code, lane.name, locale));

  return (
    <main className="market-shell">
      {catalog?.catalog_source === "snapshot" ? (
        <div className="catalog-preview-notice" role="status">
          <strong>{bn ? "ক্যাটালগ প্রিভিউ" : "Catalog preview"}</strong>
          <span>{bn ? "পণ্য দেখা যাচ্ছে। লাইভ কোট ও অর্ডার সাময়িকভাবে বন্ধ আছে।" : "Products are available to browse. Live quotes and ordering are temporarily unavailable."}</span>
        </div>
      ) : null}
      <section className="market-hero">
        <div className="hero-copy">
          <span className="hero-pill">{bn ? "AI-সহায়িত ক্রস-বর্ডার সোর্সিং" : "AI-assisted cross-border sourcing"}</span>
          <h1>{bn ? "প্রতিটি বৈশ্বিক সোর্সিং সিদ্ধান্ত নিন আত্মবিশ্বাসের সাথে।" : "Make every global sourcing decision with confidence."}</h1>
          <p>{bn ? "ল্যান্ডেড কস্ট, সাপ্লায়ারের নির্ভরযোগ্যতা, ডেলিভারির সময় ও সোর্সিং ঝুঁকি তুলনা করুন, তারপর আপনার ব্যবসার জন্য সেরা রুট বেছে নিন।" : "Compare landed cost, supplier reliability, delivery time and sourcing risk—then choose the best route for your business."}</p>
          <form action="/products" className="hero-search">
            <input name="q" placeholder={bn ? "কোন পণ্য সোর্স করতে চান?" : "What product are you sourcing?"} />
            <button>{bn ? "মার্কেটপ্লেসে খুঁজুন" : "Search marketplace"}</button>
          </form>
          <div className="hero-trust"><span><AppIcon name="check" size={15} />{catalog ? (bn ? `${count(catalog.total)}টি পণ্য` : `${catalog.total} products`) : (bn ? "বৈশ্বিক পণ্য ক্যাটালগ" : "Global product catalog")}</span><span><AppIcon name="check" size={15} />{bn ? "ব্যাখ্যাযোগ্য র‍্যাঙ্কিং" : "Explainable ranking"}</span><span><AppIcon name="check" size={15} />{bn ? "স্বচ্ছ ল্যান্ডেড কস্ট" : "Landed-cost clarity"}</span></div>
        </div>
        <div className="lane-board-new">
          <div className="lane-title"><span>{bn ? "প্রধান সোর্সিং রুট" : "Featured sourcing lanes"}</span><strong>{bn ? "এক নজরে" : "Decision snapshot"}</strong></div>
          {lanes.map((lane) => <div className="lane-item" key={lane.code}><b>{lane.code}</b><div><strong>{lane.name}</strong><span>{lane.eta}</span></div><em>{lane.badge}</em></div>)}
          <p>{otherOrigins.length ? (bn ? `ক্যাটালগে আরও আছে ${otherOrigins.join(", ")}। ` : `Catalog origins also include ${otherOrigins.join(", ")}. `) : ""}{lanes.length ? (bn ? "স্কোরে খরচ, মান, নির্ভরযোগ্যতা, ডেলিভারি ও ঝুঁকি একসাথে ধরা হয়।" : "Scores combine cost, quality, reliability, delivery and risk.") : (bn ? "রুটের তথ্য এই মুহূর্তে পাওয়া যাচ্ছে না।" : "Live lane data is temporarily unavailable.")}</p>
        </div>
      </section>

      <section className="market-section">
        <div className="market-section-title">
          <div><span className="market-kicker">{bn ? "ক্যাটাগরি অনুযায়ী" : "Browse by category"}</span><h2>{bn ? "সোর্সিংয়ের সুযোগ খুঁজুন" : "Explore sourcing opportunities"}</h2></div>
          <Link href="/products">{bn ? "সব ক্যাটাগরি দেখুন →" : "View all categories →"}</Link>
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
          <div><span className="market-kicker">{bn ? "লাইভ ক্যাটালগ" : "Live catalog"}</span><h2>{bn ? "জনপ্রিয় পণ্য" : "Popular products"}</h2></div>
          <Link href="/products">{catalog ? (bn ? `সব ${count(catalog.total)}টি দেখুন` : `Browse all ${catalog.total}`) : (bn ? "ক্যাটালগ দেখুন" : "Browse catalog")} →</Link>
        </div>
        {popularProducts.length ? <div className="compact-grid">{popularProducts.map((product, index) => <ProductCard key={product.id} product={product} imagePriority={index < 4} />)}</div> : <div className="market-empty">{bn ? "ক্যাটালগ চালু হচ্ছে। একটু পরে রিফ্রেশ করুন।" : "Catalog is starting. Please refresh shortly."}</div>}
      </section>

      <section className="decision-banner">
        <div><span className="market-kicker">{bn ? "ভালো সিদ্ধান্তের জন্য তৈরি" : "Built for better decisions"}</span><h2>{bn ? "শুধু মার্কেটপ্লেস নয়।" : "More than a marketplace."}</h2><p>{bn ? "নিজের অগ্রাধিকার ঠিক করুন, আর ব্যাখ্যাসহ সাপ্লায়ার ও দেশের সুপারিশ পান।" : "Adjust your priorities and get an explainable supplier and country recommendation."}</p></div>
        <Link href="/products">{bn ? "সোর্সিং শুরু করুন →" : "Start sourcing →"}</Link>
      </section>
    </main>
  );
}
