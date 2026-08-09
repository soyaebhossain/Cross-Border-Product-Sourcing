"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getAdminAIReviews, type AdminAIReview } from "../../../lib/admin-api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

export default function AdminAIReviewsPage() {
  const [items, setItems] = useState<AdminAIReview[]>([]);
  const [status, setStatus] = useState("PENDING");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setItems((await getAdminAIReviews(status)).items); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "AI review queue could not be loaded."); }
    finally { setLoading(false); }
  }, [status]);
  useEffect(() => { void load(); }, [load]);

  return <div className="admin-page">
    <header className="admin-page-header"><div><p className="admin-eyebrow">Human oversight</p><h1>{bn ? "AI রিভিউ কিউ" : "AI review queue"}</h1><p>{bn ? "ঝুঁকিপূর্ণ বা কম-নিশ্চয়তার sourcing explanation যাচাই করুন।" : "Review risk-sensitive sourcing explanations before relying on them."}</p></div><label><span>Status</span><select className="admin-select" value={status} onChange={event => setStatus(event.target.value)}><option value="PENDING">PENDING</option><option value="APPROVED">APPROVED</option><option value="REJECTED">REJECTED</option><option value="NOT_REQUIRED">NOT REQUIRED</option></select></label></header>
    {error ? <div className="admin-alert admin-alert--error" role="alert">{error}</div> : null}
    {loading ? <div className="admin-auth-check"><span className="admin-spinner" />Loading reviews…</div> : null}
    {!loading && !items.length ? <div className="admin-empty">No AI explanations match this status.</div> : null}
    <div className="admin-card-grid">{items.map(item => <article className="admin-card" key={item.id}><div className="admin-card__header"><div><h2>{item.product_name}</h2><p>Quote #{item.saved_quote_id} · {item.country} · {item.mode} · Qty {item.qty}</p></div><span className={`admin-status admin-status--${item.review_status.toLowerCase()}`}>{item.review_status}</span></div><p>{item.explanation.summary_bn}</p><dl className="account-definition-list"><div><dt>Provider</dt><dd>{item.provider}</dd></div><div><dt>Confidence</dt><dd>{item.confidence == null ? "Not calibrated" : `${Math.round(Number(item.confidence) * 100)}%`}</dd></div><div><dt>Created</dt><dd>{formatDateTime(item.created_at, intlLocale)}</dd></div><div><dt>Mandatory review</dt><dd>{item.human_review_required ? "Yes" : "No"}</dd></div></dl><Link className="admin-button admin-button--primary" href={`/admin/quotes/${item.saved_quote_id}`}>Review quote</Link></article>)}</div>
  </div>;
}
