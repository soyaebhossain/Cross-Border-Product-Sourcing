"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  getDelayAnalytics,
  getProfitabilityAnalytics,
  getSupplierAnalytics,
  type DelayedOrderRow,
  type ProfitabilityRow,
  type SupplierAnalyticsRow,
} from "../../../lib/admin-api";
import type { AdminListResponse } from "../../../lib/api";
import { formatCurrency, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

type View = "suppliers" | "profitability" | "delays";
type Dimension = "country" | "category" | "product";

const emptyPage = <T,>(): AdminListResponse<T> => ({ items: [], total: 0, page: 1, page_size: 25, pages: 1 });

export default function AdminAnalyticsPage() {
  const [view, setView] = useState<View>("suppliers");
  const [dimension, setDimension] = useState<Dimension>("country");
  const [days, setDays] = useState(30);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [suppliers, setSuppliers] = useState<AdminListResponse<SupplierAnalyticsRow>>(emptyPage);
  const [profitability, setProfitability] = useState<AdminListResponse<ProfitabilityRow> & { metric_definition?: string; empty_state?: string | null }>({ ...emptyPage<ProfitabilityRow>() });
  const [delays, setDelays] = useState<AdminListResponse<DelayedOrderRow>>(emptyPage);
  const [definitions, setDefinitions] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => {
    const candidate = new URLSearchParams(window.location.search).get("view");
    if (candidate === "suppliers" || candidate === "profitability" || candidate === "delays") setView(candidate);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const range = dateFrom && dateTo ? { date_from: dateFrom, date_to: dateTo } : { days };
    try {
      if (view === "suppliers") {
        const result = await getSupplierAnalytics({ ...range, timezone: "Asia/Dhaka", page, page_size: 25 });
        setSuppliers(result);
        setDefinitions(result.metric_definitions);
      } else if (view === "profitability") {
        const result = await getProfitabilityAnalytics({ ...range, timezone: "Asia/Dhaka", page, page_size: 25, dimension });
        setProfitability(result);
      } else {
        setDelays(await getDelayAnalytics({ ...range, timezone: "Asia/Dhaka", page, page_size: 25 }));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Analytics লোড করা যায়নি।" : "Analytics could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [view, dimension, days, dateFrom, dateTo, page, bn]);

  useEffect(() => { void load(); }, [load]);
  const activePage = view === "suppliers" ? suppliers : view === "profitability" ? profitability : delays;

  return <div className="admin-page">
    <header className="admin-page-header"><div><p className="admin-eyebrow">{bn ? "Drill-down analytics" : "Drill-down analytics"}</p><h1>{bn ? "পারফরম্যান্স বিশ্লেষণ" : "Performance analytics"}</h1><p>{bn ? "Supplier outcome, realized profitability এবং delayed shipment-এর source-backed detail।" : "Source-backed supplier outcomes, realized profitability and delayed-shipment detail."}</p></div><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></header>

    <div className="admin-view-tabs" role="tablist" aria-label={bn ? "Analytics view" : "Analytics view"}>
      {(["suppliers", "profitability", "delays"] as View[]).map(item => <button role="tab" aria-selected={view === item} className={view === item ? "admin-view-tab admin-view-tab--active" : "admin-view-tab"} key={item} onClick={() => { setView(item); setPage(1); }}>{item === "suppliers" ? (bn ? "Supplier SLA" : "Supplier SLA") : item === "profitability" ? (bn ? "Profitability" : "Profitability") : (bn ? "Delayed shipments" : "Delayed shipments")}</button>)}
    </div>

    <section className="admin-card admin-analytics-filters">
      <label className="admin-filter"><span>{bn ? "Quick range" : "Quick range"}</span><select value={dateFrom ? "custom" : days} onChange={event => { if (event.target.value === "custom") return; setDateFrom(""); setDateTo(""); setDays(Number(event.target.value)); setPage(1); }}><option value={1}>{bn ? "আজ" : "Today"}</option><option value={7}>{bn ? "৭ দিন" : "7 days"}</option><option value={30}>{bn ? "৩০ দিন" : "30 days"}</option><option value={90}>{bn ? "৯০ দিন" : "90 days"}</option><option value="custom">{bn ? "নিজস্ব" : "Custom"}</option></select></label>
      <label className="admin-filter"><span>{bn ? "শুরু" : "From"}</span><input type="date" value={dateFrom} max={dateTo || undefined} onChange={event => { setDateFrom(event.target.value); setPage(1); }} /></label>
      <label className="admin-filter"><span>{bn ? "শেষ" : "To"}</span><input type="date" value={dateTo} min={dateFrom || undefined} onChange={event => { setDateTo(event.target.value); setPage(1); }} /></label>
      {view === "profitability" ? <label className="admin-filter"><span>{bn ? "Dimension" : "Dimension"}</span><select value={dimension} onChange={event => { setDimension(event.target.value as Dimension); setPage(1); }}><option value="country">{bn ? "দেশ" : "Country"}</option><option value="category">{bn ? "ক্যাটাগরি" : "Category"}</option><option value="product">{bn ? "পণ্য" : "Product"}</option></select></label> : null}
      <button className="admin-button admin-button--secondary" type="button" onClick={load} disabled={loading}>{bn ? "রিফ্রেশ" : "Refresh"}</button>
    </section>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Unable to load"}</strong><span>{error}</span><button type="button" onClick={load}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}
    {loading ? <div className="admin-loading" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "Analytics লোড হচ্ছে…" : "Loading analytics…"}</div> : !error ? <section className="admin-card admin-list-card">
      <div className="admin-table-wrap"><table className="admin-data-table">
        {view === "suppliers" ? <><thead><tr><th>{bn ? "সাপ্লায়ার" : "Supplier"}</th><th>{bn ? "অর্ডার" : "Orders"}</th><th>{bn ? "Delivered" : "Delivered"}</th><th title={definitions.supplier_sla_pct}>SLA</th><th title={definitions.supplier_defect_rate_pct}>Defect</th><th title={definitions.supplier_reliability_pct}>Reliability</th></tr></thead><tbody>{suppliers.items.map(row => <tr key={row.supplier_id}><td><Link href={`/admin/suppliers/${row.supplier_id}`}>{row.supplier_name}</Link><small>★ {row.catalog_rating.toFixed(2)}</small></td><td>{row.orders}</td><td>{row.delivered_orders}</td><td>{row.sla_pct === null ? "N/A" : `${row.sla_pct.toFixed(2)}%`}</td><td>{row.defect_rate_pct === null ? "N/A" : `${row.defect_rate_pct.toFixed(2)}%`}</td><td>{row.reliability_pct === null ? "N/A" : `${row.reliability_pct.toFixed(2)}%`}</td></tr>)}</tbody></> : null}
        {view === "profitability" ? <><thead><tr><th>{dimension[0].toUpperCase() + dimension.slice(1)}</th><th>{bn ? "অর্ডার" : "Orders"}</th><th>{bn ? "Revenue" : "Revenue"}</th><th>{bn ? "Actual cost" : "Actual cost"}</th><th>{bn ? "Margin" : "Margin"}</th><th>%</th></tr></thead><tbody>{profitability.items.map(row => <tr key={row.key}><td>{row.name}</td><td>{row.orders}</td><td>{formatCurrency(row.revenue_bdt, "BDT", intlLocale)}</td><td>{formatCurrency(row.actual_cost_bdt, "BDT", intlLocale)}</td><td>{formatCurrency(row.margin_bdt, "BDT", intlLocale)}</td><td>{row.margin_pct === null ? "N/A" : `${row.margin_pct.toFixed(2)}%`}</td></tr>)}</tbody></> : null}
        {view === "delays" ? <><thead><tr><th>{bn ? "অর্ডার" : "Order"}</th><th>{bn ? "দেশ" : "Country"}</th><th>{bn ? "স্ট্যাটাস" : "Status"}</th><th>{bn ? "Promised" : "Promised"}</th><th>{bn ? "Delivered" : "Delivered"}</th><th>{bn ? "ধরন" : "Type"}</th></tr></thead><tbody>{delays.items.map(row => <tr key={row.order_id}><td><Link href={`/admin/orders/${row.order_id}`}>#{row.order_id}</Link></td><td>{row.country}</td><td><span className={`admin-status admin-status--${row.status.toLowerCase()}`}>{row.status.replaceAll("_", " ")}</span></td><td>{formatDateTime(row.promised_delivery_at, intlLocale)}</td><td>{formatDateTime(row.delivered_at, intlLocale)}</td><td>{row.delay_type.replaceAll("_", " ")}</td></tr>)}</tbody></> : null}
      </table></div>
      {!activePage.items.length ? <div className="admin-empty"><strong>{bn ? "এই সময়ে কোনো eligible row নেই।" : "No eligible rows in this window."}</strong>{view === "profitability" ? <span>{profitability.empty_state || (bn ? "Actual cost settlement প্রয়োজন।" : "Actual-cost settlement is required.")}</span> : null}</div> : null}
      <footer className="admin-pagination"><span>{activePage.total} {bn ? "row" : "rows"}</span><div><button type="button" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>{bn ? "আগের" : "Previous"}</button><span>{bn ? "পৃষ্ঠা" : "Page"} {activePage.page} / {Math.max(1, activePage.pages)}</span><button type="button" disabled={page >= activePage.pages} onClick={() => setPage(value => value + 1)}>{bn ? "পরের" : "Next"}</button></div></footer>
    </section> : null}
  </div>;
}
