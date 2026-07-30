"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import {
  addAdminSupportMessage,
  getAdminSupportTicket,
  type SupportTicket,
  updateAdminSupportStatus,
} from "../../../../lib/customer-api";
import { formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";
import { useAdminAccess } from "../../../../lib/use-admin-access";

const ticketStatuses = ["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "RESOLVED", "CLOSED"];

export default function AdminSupportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [reply, setReply] = useState("");
  const [statusDraft, setStatusDraft] = useState("");
  const [pendingStatus, setPendingStatus] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState("");
  const { locale, intlLocale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getAdminSupportTicket(id);
      setTicket(result);
      setStatusDraft(result.status);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "সাপোর্ট টিকিট লোড করা যায়নি।" : "Support ticket could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, id]);

  useEffect(() => { void load(); }, [load]);

  const submitReply = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ticket || reply.trim().length < 1) return;
    setSaving(true);
    setError("");
    try {
      const result = await addAdminSupportMessage(ticket.id, reply.trim());
      setTicket(result);
      setStatusDraft(result.status);
      setReply("");
      setToast(bn ? "উত্তর পাঠানো হয়েছে এবং কাস্টমার notification queue-তে যোগ হয়েছে।" : "Reply sent and the customer notification was queued.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "উত্তর পাঠানো যায়নি।" : "Reply could not be sent."));
    } finally {
      setSaving(false);
    }
  };

  const submitStatus = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ticket || !pendingStatus || statusNote.trim().length < 3) return;
    setSaving(true);
    setError("");
    try {
      const result = await updateAdminSupportStatus(ticket.id, pendingStatus, statusNote.trim());
      setTicket(result);
      setStatusDraft(result.status);
      setPendingStatus(null);
      setStatusNote("");
      setToast(bn ? "স্ট্যাটাস আপডেট হয়েছে এবং audit log তৈরি হয়েছে।" : "Status updated and an audit record was created.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "স্ট্যাটাস আপডেট করা যায়নি।" : "Status could not be updated."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "সাপোর্ট টিকিট লোড হচ্ছে…" : "Loading support ticket…"}</div>;
  if (!ticket) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "টিকিট পাওয়া যায়নি" : "Ticket unavailable"}</strong><span>{error}</span><button type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div></div>;

  const closed = ticket.status === "CLOSED";
  return <div className="admin-page">
    <header className="admin-page-header">
      <div>
        <Link className="account-back-link" href="/admin/support">← {bn ? "সাপোর্ট তালিকা" : "Support queue"}</Link>
        <p className="admin-eyebrow">{ticket.public_id}</p>
        <h1>{ticket.subject}</h1>
        <p>{bn ? "তৈরি" : "Created"} {formatDateTime(ticket.created_at, intlLocale)} · {bn ? "আপডেট" : "Updated"} {formatDateTime(ticket.updated_at, intlLocale)}</p>
      </div>
      <div className="admin-toolbar"><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></div>
    </header>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "অ্যাকশন ব্যর্থ" : "Action failed"}</strong><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ করুন" : "Dismiss"}</button></div> : null}
    {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}

    <section className="admin-detail-grid">
      <article className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "টিকিট তথ্য" : "Ticket information"}</h2><p>{bn ? "কাস্টমার ও request context" : "Customer and request context"}</p></div><span className={`admin-status admin-status--${ticket.status.toLowerCase()}`}>{ticket.status.replaceAll("_", " ")}</span></div>
        <dl className="account-definition-list">
          <div><dt>{bn ? "কাস্টমার" : "Customer"}</dt><dd>{isAdmin ? <Link href={`/admin/users/${ticket.user_id}`}>User #{ticket.user_id}</Link> : `User #${ticket.user_id}`}</dd></div>
          <div><dt>{bn ? "অর্ডার" : "Order"}</dt><dd>{ticket.order_id ? <Link href={`/admin/orders/${ticket.order_id}`}>Order #{ticket.order_id}</Link> : "—"}</dd></div>
          <div><dt>{bn ? "ক্যাটাগরি" : "Category"}</dt><dd>{ticket.category}</dd></div>
          <div><dt>{bn ? "অগ্রাধিকার" : "Priority"}</dt><dd><span className={`admin-status admin-status--${ticket.priority.toLowerCase()}`}>{ticket.priority}</span></dd></div>
          <div><dt>{bn ? "সমাধান হয়েছে" : "Resolved at"}</dt><dd>{formatDateTime(ticket.resolved_at, intlLocale)}</dd></div>
          <div><dt>{bn ? "বন্ধ হয়েছে" : "Closed at"}</dt><dd>{formatDateTime(ticket.closed_at, intlLocale)}</dd></div>
        </dl>
      </article>

      <article className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "স্ট্যাটাস পরিবর্তন" : "Change status"}</h2><p>{bn ? "প্রতিটি পরিবর্তনে note ও audit trail থাকবে" : "Every change requires a note and creates an audit trail"}</p></div></div>
        {closed ? <div className="admin-empty"><strong>{bn ? "টিকিটটি বন্ধ" : "Ticket is closed"}</strong><span>{bn ? "বন্ধ টিকিট terminal; আর পরিবর্তন করা যাবে না।" : "Closed tickets are terminal and cannot be changed."}</span></div> : <div className="admin-form-grid">
          <label className="admin-form-grid__wide"><span>{bn ? "নতুন স্ট্যাটাস" : "New status"}</span><select value={statusDraft} onChange={event => setStatusDraft(event.target.value)}>{ticketStatuses.map(status => <option value={status} key={status}>{status.replaceAll("_", " ")}</option>)}</select></label>
          <div className="admin-form-grid__wide admin-detail-actions"><button className="admin-button admin-button--primary" type="button" disabled={saving || statusDraft === ticket.status} onClick={() => { setPendingStatus(statusDraft); setStatusNote(""); }}>{bn ? "স্ট্যাটাস আপডেট" : "Update status"}</button></div>
        </div>}
      </article>
    </section>

    <section className="admin-card">
      <div className="admin-card__header"><div><h2>{bn ? "কথোপকথন" : "Conversation"}</h2><p>{bn ? `${ticket.messages?.length || 0}টি বার্তা` : `${ticket.messages?.length || 0} messages`}</p></div></div>
      {ticket.messages?.length ? <ol className="admin-audit-timeline">{ticket.messages.map(message => <li key={message.id}><span aria-hidden /><div><strong>{message.author_role === "customer" ? (bn ? "কাস্টমার" : "Customer") : `${message.author_role} · User #${message.author_user_id}`}</strong><p>{message.body}</p><small>{formatDateTime(message.created_at, intlLocale)}{message.request_id ? ` · Request ${message.request_id}` : ""}</small></div></li>)}</ol> : <div className="admin-empty">{bn ? "এখনও কোনো বার্তা নেই।" : "No messages yet."}</div>}
    </section>

    <section className="admin-card admin-ops-section">
      <div className="admin-card__header"><div><h2>{bn ? "কাস্টমারকে উত্তর দিন" : "Reply to customer"}</h2><p>{bn ? "উত্তরটি conversation ও notification queue—দুই জায়গাতেই সংরক্ষিত হবে।" : "The reply is stored in the conversation and queued for customer notification."}</p></div></div>
      {closed ? <div className="admin-empty">{bn ? "বন্ধ টিকিটে নতুন বার্তা দেওয়া যায় না।" : "Closed tickets cannot receive new replies."}</div> : <form className="admin-form-grid" onSubmit={submitReply}>
        <label className="admin-form-grid__wide"><span>{bn ? "উত্তর" : "Reply"}</span><textarea rows={5} minLength={1} maxLength={5000} required value={reply} onChange={event => setReply(event.target.value)} /></label>
        <div className="admin-form-grid__wide admin-detail-actions"><button className="admin-button admin-button--primary" type="submit" disabled={saving || !reply.trim()}>{saving ? (bn ? "পাঠানো হচ্ছে…" : "Sending…") : (bn ? "উত্তর পাঠান" : "Send reply")}</button></div>
      </form>}
    </section>

    <AdminModal open={pendingStatus !== null} onClose={() => !saving && setPendingStatus(null)} title={bn ? "স্ট্যাটাস পরিবর্তন নিশ্চিত করুন" : "Confirm status change"} description={`${ticket.public_id} · ${ticket.status.replaceAll("_", " ")} → ${pendingStatus?.replaceAll("_", " ") || ""}`}>
      <form className="admin-modal__form" onSubmit={submitStatus}>
        <label><span>{bn ? "আবশ্যিক audit note" : "Mandatory audit note"}</span><textarea rows={4} minLength={3} maxLength={1000} required value={statusNote} onChange={event => setStatusNote(event.target.value)} /></label>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setPendingStatus(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" type="submit" disabled={saving || statusNote.trim().length < 3}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "নিশ্চিত করুন" : "Confirm change")}</button></div>
      </form>
    </AdminModal>
  </div>;
}
