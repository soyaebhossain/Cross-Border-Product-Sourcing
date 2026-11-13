"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useState } from "react";
import { getPayables, PO_STATUS_LABELS, type PayablesReport } from "../../../../lib/admin-erp-api";
import { formatAmount, formatBdt, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

export default function SupplierPayablesPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const [report, setReport] = useState<PayablesReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getPayables().then(setReport).catch(reason => setError(reason instanceof Error ? reason.message : "Payables could not be loaded."));
  }, []);

  if (error) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Could not load"}</strong><span>{error}</span></div></div>;
  if (!report) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "পাওনার হিসাব লোড হচ্ছে…" : "Loading payables…"}</div>;

  const bucketLabel = { "0_30": bn ? "০–৩০ দিন" : "0–30 days", "31_60": bn ? "৩১–৬০ দিন" : "31–60 days", over_60: bn ? "৬০ দিনের বেশি" : "Over 60 days" };
  return <div className="admin-page">
    <header className="admin-page-header">
      <div><p className="admin-eyebrow">{bn ? "ফাইন্যান্স" : "Finance"}</p><h1>{bn ? "সাপ্লায়ারের পাওনা" : "Supplier payables"}</h1><p>{bn ? "পাঠানো, নিশ্চিত বা গ্রহণ হওয়া purchase order-এ সাপ্লায়ারের কাছে কত বাকি, বয়স অনুযায়ী।" : "What is still owed to suppliers on sent, confirmed and received purchase orders, by age."}</p></div>
      <div className="admin-toolbar"><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></div>
    </header>

    <section className="admin-kpi-grid" aria-label={bn ? "পাওনার বয়স" : "Payables aging"}>
      <article className="admin-kpi"><div><span>{bn ? "মোট বাকি" : "Total outstanding"}</span></div><strong>{formatBdt(report.total_outstanding_bdt, intlLocale)}</strong><small>{report.items.length} {bn ? "টি purchase order" : "purchase orders"}</small></article>
      {(["0_30", "31_60", "over_60"] as const).map(bucket => <article className="admin-kpi" key={bucket}><div><span>{bucketLabel[bucket]}</span></div><strong>{formatBdt(report.aging_bdt[bucket], intlLocale)}</strong><small>{report.items.filter(item => item.age_bucket === bucket).length} {bn ? "টি" : "open"}</small></article>)}
    </section>

    <section className="admin-card admin-list-card admin-ops-section">
      <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th>PO</th><th>{bn ? "সাপ্লায়ার" : "Supplier"}</th><th>{bn ? "অবস্থা" : "Status"}</th><th>{bn ? "মোট" : "Total"}</th><th>{bn ? "পরিশোধিত" : "Paid"}</th><th>{bn ? "বাকি" : "Outstanding"}</th><th>{bn ? "বাকি (BDT)" : "Outstanding (BDT)"}</th><th>{bn ? "বয়স" : "Age"}</th></tr></thead>
        <tbody>{report.items.map(item => {
          const label = PO_STATUS_LABELS[item.status];
          return <tr key={item.id}>
            <td><Link href={`/admin/procurement/${item.id}` as Route}><strong>{item.po_number}</strong></Link></td>
            <td>{item.supplier.name}</td>
            <td><span className={`admin-status admin-status--${label.tone}`}>{bn ? label.bn : label.en}</span></td>
            <td>{item.currency} {formatAmount(item.total_origin, intlLocale)}</td>
            <td>{item.currency} {formatAmount(item.paid_origin, intlLocale)}</td>
            <td><strong>{item.currency} {formatAmount(item.outstanding_origin, intlLocale)}</strong></td>
            <td>{formatBdt(item.outstanding_bdt, intlLocale)}</td>
            <td><span className={`admin-status admin-status--${item.age_bucket === "over_60" ? "high" : item.age_bucket === "31_60" ? "medium" : "low"}`}>{item.age_days} {bn ? "দিন" : "days"}</span></td>
          </tr>;
        })}</tbody>
      </table></div>
      {!report.items.length ? <div className="admin-empty"><strong>{bn ? "কোনো বাকি পাওনা নেই" : "Nothing is owed to suppliers"}</strong><span>{bn ? "সাপ্লায়ারকে purchase order পাঠানো হলে এখানে দেখাবে।" : "Purchase orders appear here once they are sent to a supplier."}</span></div> : null}
      <footer className="admin-pagination"><span>{bn ? "বাকি অঙ্ক প্রতিটি purchase order-এর বিনিময় হারে BDT-তে রূপান্তরিত।" : report.note}</span><span>{formatDateTime(report.generated_at, intlLocale)}</span></footer>
    </section>
  </div>;
}
