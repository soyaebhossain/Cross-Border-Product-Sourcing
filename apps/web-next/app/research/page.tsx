"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, getResearchAnalytics, getResearchExportUrl, type ResearchAnalytics } from "../../lib/api";
import { formatBdt } from "../../lib/format";

const labels: Record<string, string> = {
  total_products: "Products",
  total_suppliers: "Suppliers",
  pending_quotations: "Saved quotations",
  active_orders: "Active orders",
  average_landed_cost_bdt: "Avg. landed cost",
  high_risk_suppliers: "High-risk suppliers",
  quote_to_order_conversion_rate: "Quote-to-order %",
};

export default function ResearchPage() {
  const [data, setData] = useState<ResearchAnalytics | null>(null);
  const [error, setError] = useState(false);
  const [authorised, setAuthorised] = useState(false);
  const router = useRouter();

  useEffect(() => {
    let active = true;
    getCurrentUser().then(user => {
      if (!active) return;
      if (user.role !== "admin") {
        router.replace(user.role === "operator" ? "/admin" : "/account");
        return;
      }
      setAuthorised(true);
      getResearchAnalytics().then(setData).catch(() => setError(true));
    }).catch(() => router.replace("/login?portal=admin"));
    return () => { active = false; };
  }, [router]);

  if (!authorised) return <main className="shell"><div className="empty-state">Verifying admin access…</div></main>;

  return (
    <main className="shell">
      <div className="section__header">
        <div><p className="eyebrow">Research analytics</p><h2>Decision-support evidence</h2></div>
        <a className="button button--primary" href={getResearchExportUrl()}>Export CSV</a>
      </div>
      {error ? <div className="empty-state">Analytics could not be loaded. Check the FastAPI service.</div> : !data ? <div className="empty-state">Loading analytics…</div> : (
        <>
          <section className="analytics-grid">
            {Object.entries(data.cards).map(([key, value]) => (
              <article className="metric-card" key={key}>
                <span>{labels[key] || key}</span>
                <strong>{key === "average_landed_cost_bdt" ? formatBdt(value) : value}</strong>
              </article>
            ))}
          </section>
          <section className="research-grid">
            <article className="form-card">
              <p className="eyebrow">Top sourcing countries</p>
              {data.top_sourcing_countries.length ? data.top_sourcing_countries.map((row) => (
                <div className="data-row" key={row.country}><span>{row.country}</span><strong>{row.quotes} quotes</strong></div>
              )) : <p className="form-note">Save quotes to populate this ranking.</p>}
            </article>
            <article className="form-card">
              <p className="eyebrow">Evaluation readiness</p>
              {Object.entries(data.evaluation).map(([module, metrics]) => (
                <div className="evaluation-row" key={module}><strong>{module.replaceAll("_", " ")}</strong><span>{String(metrics.status)}</span></div>
              ))}
            </article>
          </section>
        </>
      )}
    </main>
  );
}
