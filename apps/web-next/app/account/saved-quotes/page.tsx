"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { deleteSavedQuote, getQuotePdfUrl, getSavedQuotes, updateSavedQuoteStatus, type SavedQuote } from "../../../lib/api";

export default function SavedQuotesPage() {
  const [quotes, setQuotes] = useState<SavedQuote[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  useEffect(() => { getSavedQuotes().then(setQuotes).catch(() => setError("Please sign in to compare saved quotes.")).finally(() => setLoading(false)); }, []);
  if (loading) return <div className="empty-state">Loading saved quotes…</div>;
  if (error) return <div className="empty-state">{error}</div>;
  if (!quotes.length) return <div className="empty-state"><strong>No saved quotes yet.</strong><p>Save a quote from the quote screen first.</p></div>;
  const remove = async (id:number) => { await deleteSavedQuote(id); setQuotes(values => values.filter(item => item.id !== id)); };
  const approve = async (id:number) => { await updateSavedQuoteStatus(id,"approved"); setQuotes(values => values.map(item => item.id===id?{...item,status:"approved"}:item)); };
  return <div className="comparison-grid">{quotes.map(quote => { const cost = quote.response?.breakdown; return <article key={quote.id} className="comparison-card">
    <span className="badge">{quote.country_id} · {quote.mode}</span><span className="quote-status">{quote.status || "requested"}</span><h3>{quote.product_name}</h3><p>{quote.variant_name} · Qty {quote.qty}</p>
    <div className="comparison-cost"><small>Total landed cost</small><strong>BDT {cost?.total_bdt || "—"}</strong></div>
    <div className="data-row"><span>Product</span><strong>{cost?.product_cost_bdt || cost?.origin_price_bdt || "—"}</strong></div>
    <div className="data-row"><span>Shipping</span><strong>{cost?.shipping_bdt || "—"}</strong></div>
    <div className="data-row"><span>Duty + VAT</span><strong>{cost?.duty_vat_bdt || "—"}</strong></div>
    <div className="data-row"><span>ETA</span><strong>{quote.response?.eta?.min_days || "—"}–{quote.response?.eta?.max_days || "—"} days</strong></div>
    <div className="form-actions"><button className="button button--primary" onClick={()=>approve(quote.id)} disabled={quote.status==="approved"}>{quote.status==="approved"?"Approved":"Approve"}</button><a className="nav-link" href={getQuotePdfUrl(quote.id)}>PDF</a><Link className="nav-link" href="/quote">Request again</Link><button className="button button--ghost" onClick={()=>remove(quote.id)}>Delete</button></div>
  </article>; })}</div>;
}
