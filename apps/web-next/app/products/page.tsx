"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ProductCard } from "../../components/product-card";
import { browseProducts, getCategories, getCountries, type Category, type Country, type ProductPage } from "../../lib/api";

export default function ProductsPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("recommended");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ProductPage | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [country, setCountry] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [delivery, setDelivery] = useState("");
  const [rating, setRating] = useState("");
  const [risk, setRisk] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [compare, setCompare] = useState<number[]>([]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQuery(params.get("q") || "");
    setCategory(params.get("category") || "");
  }, []);

  useEffect(() => {
    Promise.all([getCategories(), getCountries()]).then(([categoryRows, countryRows]) => {
      setCategories(categoryRows); setCountries(countryRows);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true); setError(null);
      browseProducts({ q: query, category, page, sort, country, maxPrice: maxPrice ? Number(maxPrice) : undefined, maxDelivery: delivery ? Number(delivery) : undefined, minRating: rating ? Number(rating) : undefined, risk })
        .then(setData).catch(() => setError("Catalog could not be loaded. Please try again."))
        .finally(() => setLoading(false));
    }, 180);
    return () => clearTimeout(timer);
  }, [query, category, page, sort, country, maxPrice, delivery, rating, risk]);

  const activeFilters = useMemo(() => [category, country, maxPrice, delivery, rating, risk].filter(Boolean).length, [category, country, maxPrice, delivery, rating, risk]);
  const toggle = (id: number) => setCompare(value => value.includes(id) ? value.filter(item => item !== id) : value.length < 3 ? [...value, id] : value);
  const reset = () => { setCategory(""); setCountry(""); setMaxPrice(""); setDelivery(""); setRating(""); setRisk(""); setSort("recommended"); setPage(1); };

  return <main className="market-shell">
    <section className="catalog-heading"><div><span className="market-kicker">Global sourcing catalog</span><h1>Find the right product and supplier</h1><p>Compare verified offers by landed cost, delivery, reliability and sourcing risk.</p></div><Link href="/quote" className="market-button">Request a quote</Link></section>
    <button className="mobile-filter-toggle" onClick={() => setFiltersOpen(value => !value)}>{filtersOpen ? "Hide filters" : `Filters${activeFilters ? ` (${activeFilters})` : ""}`}</button>
    <div className="catalog-layout">
      <aside className={filtersOpen ? "filter-panel filter-panel--open" : "filter-panel"}><div className="filter-title"><strong>Refine results</strong>{activeFilters ? <span>{activeFilters} active</span> : null}</div>
        <label>Category<select value={category} onChange={event => { setCategory(event.target.value); setPage(1); }}><option value="">All categories</option>{categories.map(item => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
        <label>Supplier country<select value={country} onChange={event => { setCountry(event.target.value); setPage(1); }}><option value="">All countries</option>{countries.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label>
        <label>Maximum unit price<input type="number" min="0" value={maxPrice} onChange={event => { setMaxPrice(event.target.value); setPage(1); }} placeholder="No maximum" /></label>
        <label>Delivery time<select value={delivery} onChange={event => { setDelivery(event.target.value); setPage(1); }}><option value="">Any delivery time</option><option value="14">Within 14 days</option><option value="30">Within 30 days</option></select></label>
        <label>Supplier rating<select value={rating} onChange={event => { setRating(event.target.value); setPage(1); }}><option value="">Any rating</option><option value="4.5">4.5 and above</option><option value="4">4.0 and above</option><option value="3.5">3.5 and above</option></select></label>
        <label>Risk level<select value={risk} onChange={event => { setRisk(event.target.value); setPage(1); }}><option value="">Any risk level</option><option>Low</option><option>Medium</option><option>High</option></select></label>
        <button className="filter-reset" onClick={reset}>Reset all filters</button>
      </aside>
      <section className="catalog-results">
        <div className="catalog-toolbar"><div><strong>{loading ? "Loading products…" : `${data?.total || 0} products`}</strong>{query ? <span>Results for “{query}”</span> : <span>Supplier-ready global catalog</span>}</div><label className="sort-control"><span>Sort by</span><select value={sort} onChange={event => setSort(event.target.value)}><option value="recommended">Recommended</option><option value="cheapest">Lowest price</option><option value="fastest">Fastest delivery</option><option value="highest_rated">Highest rated</option><option value="name">Name A–Z</option></select></label></div>
        {loading ? <div className="compact-grid">{Array.from({ length: 8 }).map((_, index) => <div className="product-skeleton" key={index} />)}</div> : error ? <div className="market-empty"><strong>Unable to load products</strong><span>{error}</span></div> : !data?.items.length ? <div className="market-empty"><strong>No matching products</strong><span>Reset filters or search using the marketplace bar above.</span></div> : <div className="compact-grid">{data.items.map(product => <ProductCard key={product.id} product={product} selectable selected={compare.includes(product.id)} onSelect={toggle} />)}</div>}
        {data && data.pages > 1 ? <div className="pagination"><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {data.pages}</span><button disabled={page === data.pages} onClick={() => setPage(value => value + 1)}>Next</button></div> : null}
      </section>
    </div>
    {compare.length ? <div className="compare-dock"><span><strong>{compare.length}</strong> selected</span><button onClick={() => setCompare([])}>Clear</button><Link href={`/quote?products=${compare.join(",")}`}>Compare sourcing</Link></div> : null}
  </main>;
}
