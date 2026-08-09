"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { decideAdminAIReview, getAdminQuoteDetail, type AdminQuoteDetail } from "../../../../lib/admin-api";
import { formatCurrency, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

export default function AdminQuoteDetailPage() {
  const params = useParams<{ id: string }>();
  const [quote, setQuote] = useState<AdminQuoteDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setQuote(await getAdminQuoteDetail(params.id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Quote could not be loaded."); }
    finally { setLoading(false); }
  }, [params.id]);

  useEffect(() => { void load(); }, [load]);

  const decideReview = async (decision: "APPROVED" | "REJECTED") => {
    if (!quote?.ai_review || reviewNote.trim().length < 3) return;
    setReviewSaving(true); setError("");
    try {
      const aiReview = await decideAdminAIReview(quote.ai_review.id, decision, reviewNote.trim());
      setQuote({ ...quote, ai_review: aiReview }); setReviewNote("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "AI review could not be saved.");
    } finally { setReviewSaving(false); }
  };

  if (loading) return <div className="admin-auth-check"><span className="admin-spinner" />{bn ? "কোট লোড হচ্ছে…" : "Loading quote…"}</div>;
  if (!quote) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert">{error || "Quote not found."}</div></div>;
  const breakdown = quote.snapshot?.breakdown;

  return <div className="admin-page">
    <header className="admin-page-header"><div><Link className="account-back-link" href="/admin/quotes">← {bn ? "কোট তালিকা" : "Quote list"}</Link><p className="admin-eyebrow">Locked quote snapshot</p><h1>{bn ? "সেভড কোট" : "Saved quote"} #{quote.id}</h1><p>{formatDateTime(quote.created_at, intlLocale)} · {quote.country} · {quote.mode}</p></div><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></header>
    {error ? <div className="admin-alert admin-alert--error" role="alert">{error}</div> : null}
    <section className="admin-detail-grid"><article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "কোট" : "Quote"}</h2><p>Customer and lifecycle</p></div><span className={`admin-status admin-status--${quote.status.toLowerCase()}`}>{quote.status}</span></div><dl className="account-definition-list">
      <div><dt>Customer</dt><dd><Link href={`/admin/users/${quote.customer.id}`}>{quote.customer.username || quote.customer.email || `User #${quote.customer.id}`}</Link></dd></div><div><dt>{bn ? "পণ্য" : "Product"}</dt><dd>{quote.product_name}</dd></div><div><dt>{bn ? "ভ্যারিয়েন্ট" : "Variant"}</dt><dd>{quote.variant_name || `#${quote.variant_id}`}</dd></div><div><dt>{bn ? "পরিমাণ" : "Quantity"}</dt><dd>{quote.qty}</dd></div><div><dt>Delivery</dt><dd>{quote.delivery_type}</dd></div><div><dt>Expiry</dt><dd>{formatDateTime(quote.expires_at, intlLocale)}</dd></div>
    </dl></article><article className="admin-card"><div className="admin-card__header"><div><h2>Price snapshot</h2><p>Not recalculated at checkout</p></div></div><dl className="account-definition-list">
      <div><dt>Product cost</dt><dd>{formatCurrency(breakdown?.product_cost_bdt || breakdown?.origin_price_bdt, "BDT", intlLocale)}</dd></div><div><dt>Shipping</dt><dd>{formatCurrency(breakdown?.shipping_bdt, "BDT", intlLocale)}</dd></div><div><dt>Duty + VAT</dt><dd>{formatCurrency(breakdown?.duty_vat_bdt, "BDT", intlLocale)}</dd></div><div><dt>Service fee</dt><dd>{formatCurrency(breakdown?.service_fee_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "মোট" : "Total"}</dt><dd>{formatCurrency(breakdown?.total_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatCurrency(breakdown?.advance_bdt, "BDT", intlLocale)}</dd></div>
    </dl></article></section>
    <section className="admin-card"><div className="admin-card__header"><div><h2>Linked orders</h2><p>Duplicate-order integrity</p></div></div>{quote.order_ids.length ? <div className="admin-inline-actions">{quote.order_ids.map(id => <Link className="admin-button admin-button--secondary" href={`/admin/orders/${id}`} key={id}>Order #{id}</Link>)}</div> : <div className="admin-empty">No order has been created from this quote.</div>}</section>
    {quote.ai_review ? <section className="admin-card"><div className="admin-card__header"><div><h2>AI sourcing explanation</h2><p>{quote.ai_review.provider} · {quote.ai_review.model || "deterministic fallback"} · {quote.ai_review.prompt_version}</p></div><span className={`admin-status admin-status--${quote.ai_review.review_status.toLowerCase()}`}>{quote.ai_review.review_status}</span></div>
      <p>{quote.ai_review.explanation.summary_bn}</p>
      <dl className="account-definition-list"><div><dt>Human review required</dt><dd>{quote.ai_review.human_review_required ? "Yes" : "No"}</dd></div><div><dt>Confidence</dt><dd>{quote.ai_review.confidence == null ? "Not calibrated" : `${Math.round(Number(quote.ai_review.confidence) * 100)}%`}</dd></div><div><dt>Reviewed by</dt><dd>{quote.ai_review.reviewed_by_user_id ? `User #${quote.ai_review.reviewed_by_user_id}` : "—"}</dd></div><div><dt>Review note</dt><dd>{quote.ai_review.review_note || "—"}</dd></div></dl>
      <div className="admin-detail-grid"><div><strong>Advantages</strong><ul>{quote.ai_review.explanation.advantages.map(item => <li key={item}>{item}</li>)}</ul></div><div><strong>Risks</strong><ul>{quote.ai_review.explanation.risks.map(item => <li key={item}>{item}</li>)}</ul></div><div><strong>Missing information</strong><ul>{quote.ai_review.explanation.missing_information.map(item => <li key={item}>{item}</li>)}</ul></div><div><strong>Recommended checks</strong><ul>{quote.ai_review.explanation.recommended_checks.map(item => <li key={item}>{item}</li>)}</ul></div></div>
      {quote.ai_review.review_status === "PENDING" ? <div className="admin-modal__form"><label><span>Mandatory review note</span><textarea rows={4} minLength={3} maxLength={2000} value={reviewNote} onChange={event => setReviewNote(event.target.value)} /></label><div className="admin-inline-actions"><button className="admin-button admin-button--primary" type="button" disabled={reviewSaving || reviewNote.trim().length < 3} onClick={() => void decideReview("APPROVED")}>Approve explanation</button><button className="admin-button admin-button--danger" type="button" disabled={reviewSaving || reviewNote.trim().length < 3} onClick={() => void decideReview("REJECTED")}>Reject explanation</button></div></div> : null}
    </section> : null}
  </div>;
}
