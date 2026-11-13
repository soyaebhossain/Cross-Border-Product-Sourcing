"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useMemo, useState } from "react";
import { ProductCard } from "../../components/product-card";
import { browseProducts, getCategories, getCountries, type Category, type Country, type ProductPage } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

export default function ProductsPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const count = (value: number) => (bn ? new Intl.NumberFormat(intlLocale).format(value) : String(value));
  const countryLabel = (item: Country) => {
    if (!bn) return item.name;
    try { return new Intl.DisplayNames(["bn"], { type: "region" }).of(item.code.toUpperCase()) || item.name; } catch { return item.name; }
  };
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("recommended");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(24);
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
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQuery(params.get("q") || "");
    setCategory(params.get("category") || "");
  }, []);

  useEffect(() => {
    const queryList = window.matchMedia("(max-width: 767px)");
    const updatePageSize = () => {
      setPageSize(queryList.matches ? 12 : 24);
      setPage(1);
    };
    updatePageSize();
    queryList.addEventListener("change", updatePageSize);
    return () => queryList.removeEventListener("change", updatePageSize);
  }, []);

  useEffect(() => {
    Promise.all([getCategories(), getCountries()]).then(([categoryRows, countryRows]) => {
      setCategories(categoryRows); setCountries(countryRows);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true); setError(null);
      browseProducts({ q: query, category, page, pageSize, sort, country, maxPrice: maxPrice ? Number(maxPrice) : undefined, maxDelivery: delivery ? Number(delivery) : undefined, minRating: rating ? Number(rating) : undefined, risk })
        .then(setData).catch(() => setError("Catalog could not be loaded. Please try again."))
        .finally(() => setLoading(false));
    }, 180);
    return () => clearTimeout(timer);
  }, [query, category, page, pageSize, sort, country, maxPrice, delivery, rating, risk, retryToken]);

  const activeFilters = useMemo(() => [category, country, maxPrice, delivery, rating, risk].filter(Boolean).length, [category, country, maxPrice, delivery, rating, risk]);
  const toggle = (id: number) => setCompare(value => value.includes(id) ? value.filter(item => item !== id) : value.length < 4 ? [...value, id] : value);
  const reset = () => { setCategory(""); setCountry(""); setMaxPrice(""); setDelivery(""); setRating(""); setRisk(""); setSort("recommended"); setPage(1); };
  const catalogPreview = data?.catalog_source === "snapshot";

  return <main className="market-shell">
    {catalogPreview ? (
      <div className="catalog-preview-notice" role="status">
        <strong>{bn ? "ক্যাটালগ প্রিভিউ" : "Catalog preview"}</strong>
        <span>{bn ? "খোঁজা ও পণ্যের বিবরণ দেখা যাচ্ছে। লাইভ কোট ও অর্ডার সাময়িকভাবে বন্ধ আছে।" : "Search and product details are available. Live quotes and ordering are temporarily unavailable."}</span>
      </div>
    ) : null}
    <section className="catalog-heading"><div><span className="market-kicker">{bn ? "বৈশ্বিক সোর্সিং ক্যাটালগ" : "Global sourcing catalog"}</span><h1>{bn ? "সঠিক পণ্য ও সাপ্লায়ার খুঁজে নিন" : "Find the right product and supplier"}</h1><p>{bn ? "ল্যান্ডেড কস্ট, ডেলিভারি, নির্ভরযোগ্যতা ও সোর্সিং ঝুঁকি দিয়ে অফার তুলনা করুন।" : "Compare verified offers by landed cost, delivery, reliability and sourcing risk."}</p></div>{catalogPreview ? <button type="button" className="market-button" disabled>{bn ? "কোট এখন বন্ধ" : "Quote unavailable"}</button> : <Link href="/quote" className="market-button">{bn ? "কোট নিন" : "Request a quote"}</Link>}</section>
    <button className="mobile-filter-toggle" onClick={() => setFiltersOpen(value => !value)}>{filtersOpen ? (bn ? "ফিল্টার লুকান" : "Hide filters") : `${bn ? "ফিল্টার" : "Filters"}${activeFilters ? ` (${count(activeFilters)})` : ""}`}</button>
    <div className="catalog-layout">
      <aside className={filtersOpen ? "filter-panel filter-panel--open" : "filter-panel"}><div className="filter-title"><strong>{bn ? "ফলাফল ছাঁকুন" : "Refine results"}</strong>{activeFilters ? <span>{bn ? `${count(activeFilters)}টি চালু` : `${activeFilters} active`}</span> : null}</div>
        <label>{bn ? "ক্যাটাগরি" : "Category"}<select value={category} onChange={event => { setCategory(event.target.value); setPage(1); }}><option value="">{bn ? "সব ক্যাটাগরি" : "All categories"}</option>{categories.map(item => <option key={item.id} value={item.slug}>{item.name}</option>)}</select></label>
        <label>{bn ? "সাপ্লায়ারের দেশ" : "Supplier country"}<select value={country} onChange={event => { setCountry(event.target.value); setPage(1); }}><option value="">{bn ? "সব দেশ" : "All countries"}</option>{countries.map(item => <option key={item.code} value={item.code}>{countryLabel(item)}</option>)}</select></label>
        <label>{bn ? "সর্বোচ্চ একক মূল্য" : "Maximum unit price"}<input type="number" min="0" value={maxPrice} onChange={event => { setMaxPrice(event.target.value); setPage(1); }} placeholder={bn ? "সীমা নেই" : "No maximum"} /></label>
        <label>{bn ? "ডেলিভারির সময়" : "Delivery time"}<select value={delivery} onChange={event => { setDelivery(event.target.value); setPage(1); }}><option value="">{bn ? "যেকোনো সময়" : "Any delivery time"}</option><option value="14">{bn ? "১৪ দিনের মধ্যে" : "Within 14 days"}</option><option value="30">{bn ? "৩০ দিনের মধ্যে" : "Within 30 days"}</option></select></label>
        <label>{bn ? "সাপ্লায়ার রেটিং" : "Supplier rating"}<select value={rating} onChange={event => { setRating(event.target.value); setPage(1); }}><option value="">{bn ? "যেকোনো রেটিং" : "Any rating"}</option><option value="4.5">{bn ? "৪.৫ বা তার বেশি" : "4.5 and above"}</option><option value="4">{bn ? "৪.০ বা তার বেশি" : "4.0 and above"}</option><option value="3.5">{bn ? "৩.৫ বা তার বেশি" : "3.5 and above"}</option></select></label>
        <label>{bn ? "ঝুঁকির মাত্রা" : "Risk level"}<select value={risk} onChange={event => { setRisk(event.target.value); setPage(1); }}><option value="">{bn ? "যেকোনো মাত্রা" : "Any risk level"}</option><option value="Low">{bn ? "কম" : "Low"}</option><option value="Medium">{bn ? "মাঝারি" : "Medium"}</option><option value="High">{bn ? "বেশি" : "High"}</option></select></label>
        <button className="filter-reset" onClick={reset}>{bn ? "সব ফিল্টার মুছুন" : "Reset all filters"}</button>
      </aside>
      <section className="catalog-results">
        <div className="catalog-toolbar"><div><strong>{loading ? (bn ? "পণ্য লোড হচ্ছে…" : "Loading products…") : bn ? `${count(data?.total || 0)}টি পণ্য` : `${data?.total || 0} ${(data?.total || 0) === 1 ? "product" : "products"}`}</strong>{query ? <span>{bn ? <>“{query}”-এর ফলাফল</> : <>Results for “{query}”</>}</span> : <span>{bn ? "সোর্সিংয়ের জন্য প্রস্তুত বৈশ্বিক ক্যাটালগ" : "Supplier-ready global catalog"}</span>}</div><label className="sort-control"><span>{bn ? "সাজান" : "Sort by"}</span><select value={sort} onChange={event => setSort(event.target.value)}><option value="recommended">{bn ? "প্রস্তাবিত" : "Recommended"}</option><option value="cheapest">{bn ? "সবচেয়ে কম দাম" : "Lowest price"}</option><option value="fastest">{bn ? "দ্রুততম ডেলিভারি" : "Fastest delivery"}</option><option value="highest_rated">{bn ? "সর্বোচ্চ রেটিং" : "Highest rated"}</option><option value="name">{bn ? "নাম A–Z" : "Name A–Z"}</option></select></label></div>
        {loading ? <div className="compact-grid">{Array.from({ length: 8 }).map((_, index) => <div className="product-skeleton" key={index} />)}</div> : error ? <div className="market-empty"><strong>{bn ? "পণ্য লোড করা যায়নি" : "Unable to load products"}</strong><span>{bn ? "ক্যাটালগ লোড করা যায়নি। আবার চেষ্টা করুন।" : error}</span><button type="button" className="button button--ghost" onClick={() => setRetryToken((value) => value + 1)}>{bn ? "আবার চেষ্টা করুন" : "Try again"}</button></div> : !data?.items.length ? <div className="market-empty"><strong>{bn ? "কোনো পণ্য পাওয়া যায়নি" : "No products found"}</strong><span>{bn ? "অন্য শব্দ, ক্যাটাগরি বা দেশ দিয়ে চেষ্টা করুন।" : "Try another keyword, category, or sourcing country."}</span><button type="button" className="button button--ghost" onClick={reset}>{bn ? "সব ফিল্টার মুছুন" : "Reset all filters"}</button></div> : <div className="compact-grid">{data.items.map((product, index) => <ProductCard key={product.id} product={product} imagePriority={index < 4} selectable selected={compare.includes(product.id)} onSelect={toggle} />)}</div>}
        {data && data.pages > 1 ? <div className="pagination"><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>{bn ? "আগের" : "Previous"}</button><span>{bn ? `পৃষ্ঠা ${count(page)} / ${count(data.pages)}` : `Page ${page} of ${data.pages}`}</span><button disabled={page === data.pages} onClick={() => setPage(value => value + 1)}>{bn ? "পরের" : "Next"}</button></div> : null}
      </section>
    </div>
    {compare.length ? <div className="compare-dock"><span><strong>{count(compare.length)}</strong>{bn ? "টি নির্বাচিত" : " selected"}</span><button onClick={() => setCompare([])}>{bn ? "মুছুন" : "Clear"}</button>{catalogPreview ? <button type="button" className="compare-unavailable" disabled>{bn ? "তুলনা এখন বন্ধ" : "Compare unavailable"}</button> : compare.length < 2 ? <button type="button" className="compare-unavailable" disabled>{bn ? "আরও ১টি বেছে নিন" : "Select 1 more"}</button> : <Link href={`/compare?products=${compare.join(",")}` as Route}>{bn ? "পণ্য তুলনা করুন" : "Compare products"}</Link>}</div> : null}
  </main>;
}
