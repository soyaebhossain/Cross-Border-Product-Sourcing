"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getAdminOverview, type AdminOverview, type AdminOverviewQuery } from "../../lib/api";
import { getAnalyticsOverview, type AnalyticsOverview } from "../../lib/admin-api";
import { formatCurrency, formatDateTime } from "../../lib/format";
import { useLocale } from "../../lib/locale-context";

type Range = "today" | 7 | 30 | 90 | "custom";

const labels: Record<string, { en: string; bn: string }> = {
  total_orders: { en: "Total orders", bn: "মোট অর্ডার" },
  active_orders: { en: "Active orders", bn: "সক্রিয় অর্ডার" },
  gross_order_value_bdt: { en: "Gross order value", bn: "মোট অর্ডার মূল্য" },
  verified_advance_bdt: { en: "Verified cash", bn: "যাচাইকৃত অর্থ" },
  verified_cash_bdt: { en: "Verified cash", bn: "যাচাইকৃত অর্থ" },
  outstanding_bdt: { en: "Outstanding", bn: "বকেয়া" },
  refunds_bdt: { en: "Refunds", bn: "রিফান্ড" },
  refunded_bdt: { en: "Refunds", bn: "রিফান্ড" },
  realized_margin_bdt: { en: "Realized margin", bn: "বাস্তবায়িত মার্জিন" },
  saved_quotes: { en: "Saved quotes", bn: "সেভড কোট" },
  products: { en: "Products", bn: "পণ্য" },
  suppliers: { en: "Suppliers", bn: "সাপ্লায়ার" },
};
const cardKeys = ["total_orders", "gross_order_value_bdt", "verified_cash_bdt", "verified_advance_bdt", "outstanding_bdt", "refunds_bdt", "realized_margin_bdt", "active_orders", "saved_quotes", "products", "suppliers"];
const metricDefinitions: Record<string, { en: string; bn: string }> = {
  total_orders: { en: "Orders created inside the selected date range.", bn: "নির্বাচিত সময়সীমায় তৈরি অর্ডার।" },
  active_orders: { en: "Current non-delivered and non-cancelled orders; this is a live snapshot.", bn: "বর্তমানে delivery বা cancel না হওয়া অর্ডার; এটি live snapshot।" },
  gross_order_value_bdt: { en: "Sum of non-cancelled order totals created in the selected range.", bn: "নির্বাচিত সময়ের non-cancelled অর্ডারের মোট মূল্য।" },
  verified_advance_bdt: { en: "Advance amounts whose payment proof was approved.", bn: "যেসব অগ্রিম payment proof অনুমোদিত হয়েছে।" },
  verified_cash_bdt: { en: "Approved cash less posted, non-reversed refunds in the selected window.", bn: "নির্বাচিত সময়ে অনুমোদিত cash থেকে posted, non-reversed refund বাদ।" },
  outstanding_bdt: { en: "Unpaid balance on eligible non-cancelled orders.", bn: "যোগ্য non-cancelled অর্ডারের অপরিশোধিত বাকি।" },
  refunds_bdt: { en: "Approved refund and reversal value in the selected range.", bn: "নির্বাচিত সময়ের অনুমোদিত refund ও reversal মূল্য।" },
  refunded_bdt: { en: "Approved refund and reversal value in the selected range.", bn: "নির্বাচিত সময়ের অনুমোদিত refund ও reversal মূল্য।" },
  realized_margin_bdt: { en: "Delivered order value less actual cost, only where actual cost was entered.", bn: "Actual cost দেওয়া delivered order-এর মূল্য থেকে actual cost বাদ।" },
  saved_quotes: { en: "Saved quotes created in the selected range.", bn: "নির্বাচিত সময়ে সংরক্ষিত কোট।" },
  products: { en: "Currently active catalog products.", bn: "বর্তমানে সক্রিয় catalog product।" },
  suppliers: { en: "Currently active suppliers.", bn: "বর্তমানে সক্রিয় supplier।" },
};

function localDate(offsetDays = 0) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value || "";
  const anchor = new Date(`${value("year")}-${value("month")}-${value("day")}T00:00:00Z`);
  anchor.setUTCDate(anchor.getUTCDate() + offsetDays);
  return anchor.toISOString().slice(0, 10);
}

type FinancialTrendRow = { date: string; orders: number; gross_bdt: string; cash_bdt: string; refunds_bdt?: string };

function TrendChart({ rows, locale, bn }: { rows: FinancialTrendRow[]; locale: string; bn: boolean }) {
  const width = 720;
  const height = 230;
  const padX = 34;
  const padY = 24;
  const values = rows.flatMap(row => [Number(row.gross_bdt) || 0, Number(row.cash_bdt) || 0, Number(row.refunds_bdt) || 0]);
  const max = Math.max(...values, 1);
  const x = (index: number) => padX + index * ((width - padX * 2) / Math.max(rows.length - 1, 1));
  const y = (value: number) => height - padY - (value / max) * (height - padY * 2);
  const orderPoints = rows.map((row, index) => `${x(index)},${y(Number(row.gross_bdt) || 0)}`).join(" ");
  const cashPoints = rows.map((row, index) => `${x(index)},${y(Number(row.cash_bdt) || 0)}`).join(" ");
  const refundPoints = rows.map((row, index) => `${x(index)},${y(Number(row.refunds_bdt) || 0)}`).join(" ");
  const labelsToShow = rows.length > 2 ? [0, Math.floor((rows.length - 1) / 2), rows.length - 1] : rows.map((_, index) => index);

  return (
    <div className="admin-chart">
      <div className="admin-chart__legend" aria-hidden><span><i className="admin-chart__key admin-chart__key--orders" />{bn ? "অর্ডার মূল্য" : "Order value"}</span><span><i className="admin-chart__key admin-chart__key--cash" />{bn ? "Verified cash" : "Verified cash"}</span><span><i className="admin-chart__key admin-chart__key--refunds" />{bn ? "Refund" : "Refunds"}</span></div>
      <svg viewBox={`0 0 ${width} ${height + 28}`} role="img" aria-label={bn ? "দিন অনুযায়ী order value, verified cash এবং refund" : "Order value, verified cash and refunds by day"}>
        {[0, .25, .5, .75, 1].map(level => <line key={level} x1={padX} x2={width - padX} y1={y(max * level)} y2={y(max * level)} className="admin-chart__grid" />)}
        <polyline points={orderPoints} className="admin-chart__line admin-chart__line--orders" />
        <polyline points={cashPoints} className="admin-chart__line admin-chart__line--cash" />
        <polyline points={refundPoints} className="admin-chart__line admin-chart__line--refunds" />
        {rows.map((row, index) => <circle key={`o-${row.date}`} cx={x(index)} cy={y(Number(row.gross_bdt) || 0)} r="3.5" className="admin-chart__point admin-chart__point--orders"><title>{`${row.date}: ${formatCurrency(row.gross_bdt, "BDT", locale)}`}</title></circle>)}
        {rows.map((row, index) => <circle key={`c-${row.date}`} cx={x(index)} cy={y(Number(row.cash_bdt) || 0)} r="3" className="admin-chart__point admin-chart__point--cash"><title>{`${row.date}: ${formatCurrency(row.cash_bdt, "BDT", locale)}`}</title></circle>)}
        {rows.map((row, index) => <circle key={`r-${row.date}`} cx={x(index)} cy={y(Number(row.refunds_bdt) || 0)} r="3" className="admin-chart__point admin-chart__point--refunds"><title>{`${row.date}: ${formatCurrency(row.refunds_bdt, "BDT", locale)}`}</title></circle>)}
        {labelsToShow.map(index => <text key={rows[index]?.date} x={x(index)} y={height + 15} textAnchor={index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"} className="admin-chart__label">{rows[index] ? new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", timeZone: "Asia/Dhaka" }).format(new Date(`${rows[index].date}T00:00:00+06:00`)) : ""}</text>)}
      </svg>
      <table className="sr-only"><caption>Daily financial values</caption><thead><tr><th>Date</th><th>Order value</th><th>Verified cash</th><th>Refunds</th></tr></thead><tbody>{rows.map(row => <tr key={row.date}><td>{row.date}</td><td>{row.gross_bdt}</td><td>{row.cash_bdt}</td><td>{row.refunds_bdt || "0.00"}</td></tr>)}</tbody></table>
    </div>
  );
}

function ProgressRows({ rows }: { rows: Array<{ label: string; value: string; percentage: number }> }) {
  return <div className="admin-progress-list">{rows.map(row => <div className="admin-progress" key={row.label}><div><span>{row.label}</span><strong>{row.value}</strong></div><div className="admin-progress__track" role="progressbar" aria-label={row.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={row.percentage}><span style={{ width: `${Math.max(0, Math.min(100, row.percentage))}%` }} /></div></div>)}</div>;
}

export default function AdminPage() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [range, setRange] = useState<Range>(30);
  const [customFrom, setCustomFrom] = useState(localDate(-29));
  const [customTo, setCustomTo] = useState(localDate());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query: 1 | 7 | 30 | 90 | AdminOverviewQuery = range === "today"
        ? 1
        : range === "custom"
          ? { date_from: customFrom, date_to: customTo, timezone: "Asia/Dhaka", compare: true }
          : range;
      const analyticsQuery = range === "custom"
        ? { date_from: customFrom, date_to: customTo, timezone: "Asia/Dhaka" }
        : { days: range === "today" ? 1 : range, timezone: "Asia/Dhaka" };
      const [operations, analytical] = await Promise.all([getAdminOverview(query), getAnalyticsOverview(analyticsQuery)]);
      setData(operations);
      setAnalytics(analytical);
    } catch {
      setError(bn ? "অপারেশন ডেটা লোড করা যায়নি। আবার চেষ্টা করুন।" : "Operations data could not be loaded. Please retry.");
    } finally {
      setLoading(false);
    }
  }, [range, customFrom, customTo, bn]);

  useEffect(() => { load(); }, [load]);

  const cards = useMemo(() => {
    if (!data) return [];
    const merged = { ...data.cards, ...(analytics?.cards || {}) };
    return cardKeys.filter(key => key in merged).map(key => [key, merged[key]] as const);
  }, [data, analytics]);
  const trendRows = useMemo<FinancialTrendRow[]>(() => analytics?.daily_financials?.map(row => ({
    date: row.date,
    orders: row.orders,
    gross_bdt: row.gross_order_value_bdt,
    cash_bdt: row.verified_cash_bdt,
    refunds_bdt: row.refunds_bdt,
  })) || data?.daily_revenue.map(row => ({
    date: row.date,
    orders: row.orders,
    gross_bdt: row.order_value_bdt,
    cash_bdt: row.verified_advance_bdt,
    refunds_bdt: "0.00",
  })) || [], [analytics, data]);

  return (
    <div className="admin-page">
      <header className="admin-page-header">
        <div><p className="admin-eyebrow">{bn ? "অপারেশন ও পারফরম্যান্স" : "Operations & performance"}</p><h1>{bn ? "কন্ট্রোল সেন্টার" : "Control center"}</h1><p>{bn ? "অর্ডার, ক্যাশ ফ্লো, সোর্সিং ও ঝুঁকির লাইভ অবস্থা।" : "A live view of orders, cash flow, sourcing and operational risk."}</p></div>
        <div className="admin-toolbar">
          <label className="admin-range-label"><span>{bn ? "সময়সীমা" : "Date range"}</span><select value={range} onChange={event => { const value = event.target.value; setRange(value === "today" || value === "custom" ? value : Number(value) as 7 | 30 | 90); }}><option value="today">{bn ? "আজ" : "Today"}</option><option value={7}>{bn ? "গত ৭ দিন" : "Last 7 days"}</option><option value={30}>{bn ? "গত ৩০ দিন" : "Last 30 days"}</option><option value={90}>{bn ? "গত ৯০ দিন" : "Last 90 days"}</option><option value="custom">{bn ? "নিজস্ব তারিখ" : "Custom dates"}</option></select></label>
          {range === "custom" ? <div className="admin-date-range" role="group" aria-label={bn ? "নিজস্ব তারিখ সীমা" : "Custom date range"}><label className="admin-range-label"><span>{bn ? "শুরু" : "From"}</span><input type="date" value={customFrom} max={customTo} onChange={event => setCustomFrom(event.target.value)} /></label><label className="admin-range-label"><span>{bn ? "শেষ" : "To"}</span><input type="date" value={customTo} min={customFrom} max={localDate()} onChange={event => setCustomTo(event.target.value)} /></label></div> : null}
          <button className="admin-button admin-button--secondary" type="button" onClick={load} disabled={loading}>{loading ? (bn ? "রিফ্রেশ হচ্ছে…" : "Refreshing…") : (bn ? "রিফ্রেশ" : "Refresh")}</button>
        </div>
      </header>

      {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Unable to load"}</strong><span>{error}</span><button type="button" onClick={load}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}
      {loading && !data ? <div className="admin-loading" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "ড্যাশবোর্ড লোড হচ্ছে…" : "Loading dashboard…"}</div> : data ? (
        <>
          <section className="admin-kpi-grid" aria-label={bn ? "মূল সূচক" : "Key performance indicators"}>
            {cards.map(([key, value]) => {
              const comparison = analytics?.comparison?.[key]?.change_percent ?? data.comparison?.[key]?.change_percent;
              const snapshot = ["active_orders", "products", "suppliers"].includes(key);
              const definition = metricDefinitions[key];
              return <article className="admin-kpi" key={key}><div><span>{bn ? labels[key]?.bn : labels[key]?.en}</span><div className="admin-kpi__context">{definition ? <button className="admin-info" type="button" title={bn ? definition.bn : definition.en} aria-label={`${bn ? labels[key]?.bn : labels[key]?.en}: ${bn ? definition.bn : definition.en}`}>i</button> : null}{comparison !== undefined && comparison !== null ? <em className={comparison >= 0 ? "admin-trend admin-trend--up" : "admin-trend admin-trend--down"} title={bn ? "আগের সমান সময়সীমার তুলনায়" : "Compared with the previous equal-length period"}>{comparison >= 0 ? "↑" : "↓"} {Math.abs(comparison).toFixed(1)}%</em> : null}</div></div><strong>{key.endsWith("_bdt") ? formatCurrency(value, "BDT", intlLocale) : new Intl.NumberFormat(intlLocale).format(Number(value) || 0)}</strong><small>{snapshot ? (bn ? "বর্তমান snapshot" : "Current snapshot") : `${data.range?.date_from || "—"} → ${data.range?.date_to || "—"}`}</small></article>;
            })}
          </section>

          <section className="admin-dashboard-grid">
            <article className="admin-card admin-card--chart">
              <div className="admin-card__header"><div><h2>{bn ? "অর্ডার মূল্য ও যাচাইকৃত অর্থ" : "Order value and verified cash"}</h2><p>{bn ? "দৈনিক BDT; বাতিল অর্ডার বাদ" : "Daily BDT; cancelled orders excluded"}</p></div><Link href="/admin/payments">{bn ? "পেমেন্ট দেখুন" : "View payments"} →</Link></div>
              {trendRows.length >= 2 ? <TrendChart rows={trendRows} locale={intlLocale} bn={bn} /> : <div className="admin-empty">{bn ? "ট্রেন্ড দেখাতে আরও অর্ডার ডেটা প্রয়োজন।" : "More order data is needed for a trend."}</div>}
            </article>
            <article className="admin-card">
              <div className="admin-card__header"><div><h2>{bn ? "অর্ডার স্টেজ" : "Orders by stage"}</h2><p>{bn ? "বর্তমান অর্ডার বিতরণ" : "Current order distribution"}</p></div><Link href="/admin/orders">{bn ? "ম্যানেজ" : "Manage"} →</Link></div>
              <ProgressRows rows={data.order_stages.filter(row => row.count > 0).map(row => ({ label: row.status.replaceAll("_", " "), value: String(row.count), percentage: row.percentage }))} />
              {!data.order_stages.some(row => row.count > 0) ? <div className="admin-empty">{bn ? "এখনও কোনো অর্ডার নেই।" : "No orders yet."}</div> : null}
            </article>
          </section>

          {analytics ? <section className="admin-analytics-grid">
            <article className="admin-card">
              <div className="admin-card__header"><div><h2>{bn ? "Quote → order → delivered funnel" : "Quote → order → delivered funnel"}</h2><p title={analytics.metric_definitions.quote_to_order_conversion_pct}>{bn ? "একই সময়ে তৈরি quote-এর linked conversion" : "Linked conversion for quotes created in the same window"}</p></div><Link href="/admin/quotes">{bn ? "কোট drill-down" : "Quote drill-down"} →</Link></div>
              <ProgressRows rows={[
                { label: bn ? "সেভড কোট" : "Saved quotes", value: String(analytics.funnel.saved_quotes), percentage: 100 },
                { label: `${bn ? "অর্ডার হয়েছে" : "Ordered"} · ${analytics.funnel.quote_to_order_conversion_pct === null ? "N/A" : `${analytics.funnel.quote_to_order_conversion_pct.toFixed(1)}%`}`, value: String(analytics.funnel.ordered_quotes), percentage: analytics.funnel.quote_to_order_conversion_pct || 0 },
                { label: `${bn ? "ডেলিভারড" : "Delivered"} · ${analytics.funnel.quote_to_delivered_conversion_pct === null ? "N/A" : `${analytics.funnel.quote_to_delivered_conversion_pct.toFixed(1)}%`}`, value: String(analytics.funnel.delivered_quotes), percentage: analytics.funnel.quote_to_delivered_conversion_pct || 0 },
              ]} />
            </article>
            <article className="admin-card">
              <div className="admin-card__header"><div><h2>{bn ? "ডেলিভারি পারফরম্যান্স" : "Delivery performance"}</h2><p title={analytics.metric_definitions.average_delivery_days}>{bn ? "Recorded timestamp-ভিত্তিক metric" : "Metrics based on recorded timestamps"}</p></div><Link href="/admin/analytics?view=delays">{bn ? "বিলম্ব দেখুন" : "View delays"} →</Link></div>
              <div className="admin-mini-metrics">
                <div><span>{bn ? "গড় delivery" : "Average delivery"}</span><strong>{analytics.delivery.average_delivery_days === null ? "N/A" : `${analytics.delivery.average_delivery_days.toFixed(2)} ${bn ? "দিন" : "days"}`}</strong><small>{analytics.coverage.delivered_with_timestamp} {bn ? "টি timestamp" : "with timestamps"}</small></div>
                <div><span>{bn ? "বিলম্বিত shipment" : "Delayed shipments"}</span><strong>{analytics.delivery.delayed_shipments}</strong><small>{analytics.delivery.delivered_late} {bn ? "late delivered" : "delivered late"} · {analytics.delivery.active_overdue} {bn ? "overdue" : "overdue"}</small></div>
              </div>
            </article>
          </section> : null}

          {analytics ? <section className="admin-dashboard-grid">
            <article className="admin-card">
              <div className="admin-card__header"><div><h2>{bn ? "সাপ্লায়ার SLA ও quality" : "Supplier SLA and quality"}</h2><p>{bn ? "Outcome না থাকলে metric N/A" : "Metrics are N/A until outcomes exist"}</p></div><Link href="/admin/analytics?view=suppliers">{bn ? "সব সাপ্লায়ার" : "All suppliers"} →</Link></div>
              <div className="admin-table-wrap"><table className="admin-data-table"><thead><tr><th>{bn ? "সাপ্লায়ার" : "Supplier"}</th><th>{bn ? "অর্ডার" : "Orders"}</th><th title={analytics.metric_definitions.supplier_sla_pct}>SLA</th><th title={analytics.metric_definitions.supplier_defect_rate_pct}>{bn ? "Defect" : "Defect"}</th><th title={analytics.metric_definitions.supplier_reliability_pct}>{bn ? "Reliability" : "Reliability"}</th></tr></thead><tbody>{analytics.supplier_performance.slice(0, 6).map(row => <tr key={row.supplier_id}><td><Link href={`/admin/suppliers/${row.supplier_id}`}> {row.supplier_name}</Link></td><td>{row.orders}</td><td>{row.sla_pct === null ? "N/A" : `${row.sla_pct.toFixed(1)}%`}</td><td>{row.defect_rate_pct === null ? "N/A" : `${row.defect_rate_pct.toFixed(1)}%`}</td><td>{row.reliability_pct === null ? "N/A" : `${row.reliability_pct.toFixed(1)}%`}</td></tr>)}</tbody></table></div>
              {!analytics.supplier_performance.length ? <div className="admin-empty">{bn ? "এই সময়ে supplier-linked outcome নেই।" : "No supplier-linked outcomes in this window."}</div> : null}
            </article>
            <article className="admin-card">
              <div className="admin-card__header"><div><h2>{bn ? "দেশ অনুযায়ী profitability" : "Profitability by country"}</h2><p title={analytics.metric_definitions.realized_margin_bdt}>{bn ? "শুধু actual cost-সহ delivered order" : "Delivered orders with actual cost only"}</p></div><Link href="/admin/analytics?view=profitability">{bn ? "Category/product drill-down" : "Category/product drill-down"} →</Link></div>
              <div className="admin-table-wrap"><table className="admin-data-table"><thead><tr><th>{bn ? "দেশ" : "Country"}</th><th>{bn ? "অর্ডার" : "Orders"}</th><th>{bn ? "Revenue" : "Revenue"}</th><th>{bn ? "Margin" : "Margin"}</th><th>%</th></tr></thead><tbody>{analytics.profitability_by_country.slice(0, 6).map(row => <tr key={row.key}><td>{row.name}</td><td>{row.orders}</td><td>{formatCurrency(row.revenue_bdt, "BDT", intlLocale)}</td><td>{formatCurrency(row.margin_bdt, "BDT", intlLocale)}</td><td>{row.margin_pct === null ? "N/A" : `${row.margin_pct.toFixed(1)}%`}</td></tr>)}</tbody></table></div>
              {!analytics.profitability_by_country.length ? <div className="admin-empty">{bn ? "Actual-cost settlement না থাকায় profitability উপলভ্য নয়।" : "Profitability is unavailable until actual-cost settlement exists."}</div> : null}
            </article>
          </section> : null}

          <section className="admin-action-grid">
            <article className="admin-card admin-action-card"><span className="admin-action-card__count">{data.payment_queue_total ?? data.payment_queue.length}</span><div><h2>{bn ? "পেমেন্ট অপেক্ষমাণ" : "Payments awaiting review"}</h2><p>{bn ? "প্রমাণ যাচাই করে approve অথবা reject করুন।" : "Review proof and approve or reject with an audit reason."}</p></div><Link className="admin-button admin-button--primary" href="/admin/payments">{bn ? "রিভিউ করুন" : "Review queue"}</Link></article>
            <article className="admin-card admin-action-card"><span className="admin-action-card__count">{data.supplier_alerts.filter(item => item.risk !== "Low").length}</span><div><h2>{bn ? "সাপ্লায়ার ঝুঁকি" : "Supplier risk alerts"}</h2><p>{bn ? "মাঝারি ও উচ্চ-ঝুঁকির সরবরাহকারী।" : "Suppliers requiring a reliability review."}</p></div><Link className="admin-button admin-button--secondary" href="/admin/suppliers">{bn ? "সাপ্লায়ার দেখুন" : "View suppliers"}</Link></article>
          </section>

          <section className="admin-card">
            <div className="admin-card__header"><div><h2>{bn ? "সাম্প্রতিক অর্ডার" : "Recent orders"}</h2><p>{bn ? "সর্বশেষ অপারেশনাল অ্যাক্টিভিটি" : "Latest operational activity"}</p></div><Link href="/admin/orders">{bn ? "সব অর্ডার" : "All orders"} →</Link></div>
            <div className="admin-table-wrap"><table className="admin-data-table"><thead><tr><th scope="col">{bn ? "অর্ডার" : "Order"}</th><th scope="col">{bn ? "রুট" : "Route"}</th><th scope="col">{bn ? "স্ট্যাটাস" : "Status"}</th><th scope="col">{bn ? "পেমেন্ট" : "Payment"}</th><th scope="col">{bn ? "মূল্য" : "Value"}</th></tr></thead><tbody>{data.recent_orders.map(order => <tr key={order.id}><td><Link href={`/admin/orders?q=${order.id}`}>#{order.id}</Link><small>User #{order.user_id}</small></td><td>{order.country} · {order.mode}</td><td><span className={`admin-status admin-status--${order.status.toLowerCase()}`}>{order.status.replaceAll("_", " ")}</span></td><td>{order.payment_verified ? <span className="admin-status admin-status--verified">{bn ? "যাচাইকৃত" : "Verified"}</span> : <span className="admin-status admin-status--pending">{bn ? "অপেক্ষমাণ" : "Pending"}</span>}</td><td>{formatCurrency(order.total_bdt, "BDT", intlLocale)}</td></tr>)}</tbody></table></div>
            {!data.recent_orders.length ? <div className="admin-empty">{bn ? "এখনও কোনো অর্ডার নেই।" : "No orders have been placed yet."}</div> : null}
          </section>

          <p className="admin-freshness">{bn ? "ডেটা সর্বশেষ আপডেট" : "Data last updated"}: {formatDateTime(analytics?.data_last_updated_at || data.range?.generated_at || data.freshness || new Date(), intlLocale)} · {analytics?.range.timezone || data.range?.timezone || "Asia/Dhaka"} · {analytics ? `Metric ${analytics.metric_version}` : ""}{analytics?.cache ? ` · cache ${analytics.cache.hit ? "hit" : "miss"} / ${analytics.cache.ttl_seconds}s TTL` : ""}</p>
        </>
      ) : null}
    </div>
  );
}
