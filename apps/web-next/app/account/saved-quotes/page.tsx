"use client";

import type { Route } from "next";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import { deleteSavedQuote, getQuotePdfUrl, getSavedQuotes, updateSavedQuoteStatus, type SavedQuote } from "../../../lib/api";
import { formatBdt, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

function isExpired(quote: SavedQuote) {
  return Boolean(quote.expires_at && new Date(quote.expires_at).getTime() < Date.now());
}

export default function SavedQuotesPage() {
  const [quotes, setQuotes] = useState<SavedQuote[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3200);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setQuotes(await getSavedQuotes());
    } catch {
      setError(bn ? "সেভড কোট লোড করা যায়নি।" : "Saved quotes could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [bn]);

  useEffect(() => { void load(); }, [load]);

  const selectedQuotes = useMemo(() => quotes.filter(quote => selected.has(quote.id)), [quotes, selected]);
  const selectedTotals = selectedQuotes.map(quote => Number(quote.response?.breakdown?.total_bdt)).filter(Number.isFinite);
  const lowestSelected = selectedTotals.length ? Math.min(...selectedTotals) : null;

  const remove = async () => {
    if (!deleteId) return;
    setBusyId(deleteId);
    try {
      await deleteSavedQuote(deleteId);
      setQuotes(values => values.filter(item => item.id !== deleteId));
      setSelected(values => { const next = new Set(values); next.delete(deleteId); return next; });
      notify(bn ? "কোট মুছে ফেলা হয়েছে।" : "Quote deleted.");
      setDeleteId(null);
    } catch {
      setError(bn ? "কোট মুছে ফেলা যায়নি।" : "Quote could not be deleted.");
    } finally {
      setBusyId(null);
    }
  };

  const approve = async (id: number) => {
    setBusyId(id);
    try {
      await updateSavedQuoteStatus(id, "approved");
      setQuotes(values => values.map(item => item.id === id ? { ...item, status: "approved" } : item));
      notify(bn ? "কোটটি পছন্দের হিসেবে চিহ্নিত হয়েছে।" : "Quote marked as preferred.");
    } catch {
      setError(bn ? "কোটের status আপডেট করা যায়নি।" : "Quote status could not be updated.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div><p className="eyebrow">{bn ? "কোট তুলনা" : "Quote comparison"}</p><h1>{bn ? "সেভড কোট" : "Saved quotes"}</h1><p>{bn ? "তুলনার জন্য ২–৩টি কোট বেছে নিন, তারপর পছন্দের কোট থেকে অর্ডার করুন।" : "Select two or three quotes to compare, then order from your preferred quote."}</p></div>
        <Link className="button button--primary" href="/quote">{bn ? "নতুন কোট নিন" : "Request a new quote"}</Link>
      </header>

      {error ? <div className="account-alert account-alert--danger" role="alert"><span>{error}</span><button type="button" onClick={load}>{bn ? "আবার চেষ্টা করুন" : "Retry"}</button></div> : null}
      {selected.size ? <div className="account-compare-bar" role="status"><strong>{new Intl.NumberFormat(intlLocale).format(selected.size)} {bn ? "টি কোট তুলনায়" : "quotes selected"}</strong><span>{bn ? "নীল border-এ তুলনার কোট এবং Best value চিহ্নিত করা হয়েছে।" : "Compared quotes use a blue border; the lowest selected total is marked Best value."}</span><button type="button" onClick={() => setSelected(new Set())}>{bn ? "নির্বাচন সরান" : "Clear selection"}</button></div> : null}

      {loading ? <div className="empty-state" aria-live="polite">{bn ? "সেভড কোট লোড হচ্ছে…" : "Loading saved quotes…"}</div>
        : !quotes.length ? <div className="empty-state"><strong>{bn ? "এখনও কোনো সেভড কোট নেই।" : "No saved quotes yet."}</strong><p>{bn ? "Quote screen থেকে Save for comparison চাপুন; কোটটি এখানে আসবে।" : "Choose Save for comparison on the quote screen; it will appear here."}</p><Link className="button button--primary" href="/quote">{bn ? "কোট নিন" : "Request a quote"}</Link></div>
        : <div className="comparison-grid">{quotes.map(quote => {
          const cost = quote.response?.breakdown;
          const expired = isExpired(quote);
          const ordered = Boolean(quote.order_ids?.length);
          const total = Number(cost?.total_bdt);
          const best = selected.has(quote.id) && lowestSelected !== null && total === lowestSelected;
          return <article key={quote.id} className={`comparison-card ${selected.has(quote.id) ? "comparison-card--selected" : ""} ${expired ? "comparison-card--expired" : ""}`}>
            <div className="comparison-card__top"><label className="comparison-select"><input type="checkbox" checked={selected.has(quote.id)} disabled={!selected.has(quote.id) && selected.size >= 3} onChange={event => setSelected(current => { const next = new Set(current); if (event.target.checked) next.add(quote.id); else next.delete(quote.id); return next; })} /><span>{bn ? "তুলনা করুন" : "Compare"}</span></label><div>{best ? <span className="badge">{bn ? "সেরা মূল্য" : "Best value"}</span> : null}<span className={`admin-status admin-status--${expired ? "expired" : (quote.status || "requested").toLowerCase()}`}>{expired ? "EXPIRED" : (quote.status || "requested").toUpperCase()}</span></div></div>
            <small>{bn ? "কোট" : "Quote"} #{quote.id} · {formatDateTime(quote.created_at, intlLocale)}</small>
            <h2>{quote.product_name}</h2><p>{quote.variant_name || "Standard"} · {bn ? "পরিমাণ" : "Qty"} {new Intl.NumberFormat(intlLocale).format(quote.qty)}</p>
            <span className="badge">{quote.country_id} · {quote.mode}</span>
            <div className="comparison-cost"><small>{bn ? "মোট ল্যান্ডেড কস্ট" : "Total landed cost"}</small><strong>{formatBdt(cost?.total_bdt, intlLocale)}</strong></div>
            <dl className="comparison-breakdown">
              <div><dt>{bn ? "পণ্য" : "Product"}</dt><dd>{formatBdt(cost?.product_cost_bdt || cost?.origin_price_bdt, intlLocale)}</dd></div>
              <div><dt>{bn ? "শিপিং" : "Shipping"}</dt><dd>{formatBdt(cost?.shipping_bdt, intlLocale)}</dd></div>
              <div><dt>{bn ? "শুল্ক + VAT" : "Duty + VAT"}</dt><dd>{formatBdt(cost?.duty_vat_bdt, intlLocale)}</dd></div>
              <div><dt>ETA</dt><dd>{quote.response?.eta?.min_days ?? "—"}–{quote.response?.eta?.max_days ?? "—"} {bn ? "দিন" : "days"}</dd></div>
              <div><dt>{bn ? "মেয়াদ শেষ" : "Expires"}</dt><dd>{formatDateTime(quote.expires_at, intlLocale)}</dd></div>
            </dl>
            {ordered ? <div className="account-alert"><span>{bn ? `এই কোট থেকে অর্ডার #${quote.order_ids?.join(", #")} তৈরি হয়েছে।` : `Order #${quote.order_ids?.join(", #")} was created from this quote.`}</span></div> : null}
            <div className="form-actions">
              {expired || ordered ? <button className="button button--primary" type="button" disabled>{expired ? (bn ? "কোটের মেয়াদ শেষ" : "Quote expired") : (bn ? "অর্ডার তৈরি হয়েছে" : "Order created")}</button> : <Link className="button button--primary" href={`/account/saved-quotes/${quote.id}/order` as Route}>{bn ? "অর্ডার করুন" : "Proceed to order"}</Link>}
              <button className="button button--ghost" type="button" onClick={() => approve(quote.id)} disabled={busyId === quote.id || quote.status === "approved" || expired}>{quote.status === "approved" ? (bn ? "পছন্দের কোট" : "Preferred") : (bn ? "পছন্দ করুন" : "Mark preferred")}</button>
              <a className="nav-link" href={getQuotePdfUrl(quote.id)}>{bn ? "PDF ডাউনলোড" : "Download PDF"}</a>
              <button className="button button--ghost button--danger-text" type="button" onClick={() => setDeleteId(quote.id)} disabled={busyId === quote.id}>{bn ? "মুছুন" : "Delete"}</button>
            </div>
          </article>;
        })}</div>}

      <AdminModal open={deleteId !== null} onClose={() => busyId === null && setDeleteId(null)} title={bn ? "সেভড কোট মুছবেন?" : "Delete saved quote?"} description={bn ? "এই কাজটি ফিরিয়ে আনা যাবে না। বিদ্যমান অর্ডার মুছে যাবে না।" : "This cannot be undone. Any existing order will remain unchanged."}>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setDeleteId(null)} disabled={busyId !== null}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--danger" type="button" onClick={remove} disabled={busyId !== null}>{busyId !== null ? (bn ? "মুছছে…" : "Deleting…") : (bn ? "মুছে ফেলুন" : "Delete quote")}</button></div>
      </AdminModal>
      {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
    </div>
  );
}
