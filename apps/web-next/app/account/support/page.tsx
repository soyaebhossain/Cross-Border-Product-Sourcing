"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import {
  addCustomerSupportMessage,
  cancelCustomerDispute,
  createCustomerDispute,
  createCustomerSupportTicket,
  getCustomerDispute,
  getCustomerSupportTicket,
  listCustomerDisputes,
  listCustomerSupportTickets,
  type CustomerDispute,
  type SupportTicket,
} from "../../../lib/customer-api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

const pageSize = 10;
const emptyTicket = { subject: "", category: "ORDER", priority: "NORMAL", message: "", order_id: "" };
const emptyDispute = { order_id: "", dispute_type: "PAYMENT", description: "", requested_resolution: "" };

export default function SupportPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [ticketTotal, setTicketTotal] = useState(0);
  const [ticketOffset, setTicketOffset] = useState(0);
  const [ticketStatus, setTicketStatus] = useState("");
  const [disputes, setDisputes] = useState<CustomerDispute[]>([]);
  const [disputeTotal, setDisputeTotal] = useState(0);
  const [disputeOffset, setDisputeOffset] = useState(0);
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [selectedDispute, setSelectedDispute] = useState<CustomerDispute | null>(null);
  const [ticketFormOpen, setTicketFormOpen] = useState(false);
  const [disputeFormOpen, setDisputeFormOpen] = useState(false);
  const [ticketForm, setTicketForm] = useState(emptyTicket);
  const [disputeForm, setDisputeForm] = useState(emptyDispute);
  const [reply, setReply] = useState("");
  const [cancelTarget, setCancelTarget] = useState<CustomerDispute | null>(null);
  const [cancelNote, setCancelNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [ticketResult, disputeResult] = await Promise.all([
        listCustomerSupportTickets({ status: ticketStatus || undefined, limit: pageSize, offset: ticketOffset }),
        listCustomerDisputes(pageSize, disputeOffset),
      ]);
      setTickets(ticketResult.items);
      setTicketTotal(ticketResult.total);
      setDisputes(disputeResult.items);
      setDisputeTotal(disputeResult.total);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "সাপোর্ট ডেটা লোড করা যায়নি।" : "Support data could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, disputeOffset, ticketOffset, ticketStatus]);

  useEffect(() => { void load(); }, [load]);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  };

  const openTicket = async (ticket: SupportTicket) => {
    setSelectedTicket(ticket);
    setReply("");
    setDetailLoading(true);
    setError("");
    try {
      setSelectedTicket(await getCustomerSupportTicket(ticket.id));
    } catch (reason) {
      setSelectedTicket(null);
      setError(reason instanceof Error ? reason.message : (bn ? "টিকিটের বিস্তারিত লোড করা যায়নি।" : "Ticket details could not be loaded."));
    } finally {
      setDetailLoading(false);
    }
  };

  const openDispute = async (dispute: CustomerDispute) => {
    setSelectedDispute(dispute);
    setDetailLoading(true);
    setError("");
    try {
      setSelectedDispute(await getCustomerDispute(dispute.id));
    } catch (reason) {
      setSelectedDispute(null);
      setError(reason instanceof Error ? reason.message : (bn ? "Dispute-এর বিস্তারিত লোড করা যায়নি।" : "Dispute details could not be loaded."));
    } finally {
      setDetailLoading(false);
    }
  };

  const createTicket = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const ticket = await createCustomerSupportTicket({
        subject: ticketForm.subject.trim(),
        category: ticketForm.category,
        priority: ticketForm.priority,
        message: ticketForm.message.trim(),
        order_id: ticketForm.order_id ? Number(ticketForm.order_id) : undefined,
      });
      setTicketFormOpen(false);
      setTicketForm(emptyTicket);
      setTicketOffset(0);
      setSelectedTicket(ticket);
      notify(bn ? "সাপোর্ট টিকিট খোলা হয়েছে।" : "Support ticket opened.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "টিকিট খোলা যায়নি।" : "Ticket could not be opened."));
    } finally {
      setSaving(false);
    }
  };

  const submitReply = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedTicket) return;
    setSaving(true);
    setError("");
    try {
      setSelectedTicket(await addCustomerSupportMessage(selectedTicket.id, reply.trim()));
      setReply("");
      notify(bn ? "উত্তর পাঠানো হয়েছে।" : "Reply sent.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "উত্তর পাঠানো যায়নি।" : "Reply could not be sent."));
    } finally {
      setSaving(false);
    }
  };

  const createDispute = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const dispute = await createCustomerDispute({
        order_id: Number(disputeForm.order_id),
        dispute_type: disputeForm.dispute_type,
        description: disputeForm.description.trim(),
        requested_resolution: disputeForm.requested_resolution.trim(),
      });
      setDisputeFormOpen(false);
      setDisputeForm(emptyDispute);
      setDisputeOffset(0);
      setSelectedDispute(dispute);
      notify(bn ? "Dispute জমা হয়েছে।" : "Dispute submitted.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Dispute জমা দেওয়া যায়নি।" : "Dispute could not be submitted."));
    } finally {
      setSaving(false);
    }
  };

  const cancelDispute = async () => {
    if (!cancelTarget) return;
    setSaving(true);
    setError("");
    try {
      const updated = await cancelCustomerDispute(cancelTarget.id, cancelNote.trim());
      setCancelTarget(null);
      setCancelNote("");
      setSelectedDispute(current => current?.id === updated.id ? updated : current);
      notify(bn ? "Dispute বাতিল হয়েছে।" : "Dispute cancelled.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Dispute বাতিল করা যায়নি।" : "Dispute could not be cancelled."));
    } finally {
      setSaving(false);
    }
  };

  const activeDispute = (status: string) => ["OPEN", "UNDER_REVIEW"].includes(status);

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div>
          <p className="eyebrow">{bn ? "সহায়তা ও সমাধান" : "Help and resolution"}</p>
          <h1>{bn ? "সাপোর্ট ও dispute" : "Support and disputes"}</h1>
          <p>{bn ? "Order-linked ticket খুলুন, staff reply দেখুন এবং formal dispute ট্র্যাক করুন।" : "Open order-linked tickets, review staff replies and track formal disputes."}</p>
        </div>
        <div className="account-inline-actions"><button className="button button--ghost" type="button" onClick={() => { setError(""); setTicketForm(emptyTicket); setTicketFormOpen(true); }}>{bn ? "নতুন টিকিট" : "New ticket"}</button><button className="button button--primary" type="button" onClick={() => { setError(""); setDisputeForm(emptyDispute); setDisputeFormOpen(true); }}>{bn ? "Dispute খুলুন" : "Open dispute"}</button></div>
      </header>

      {error ? <div className="account-alert account-alert--danger" role="alert"><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}

      <section className="account-panel">
        <div className="account-panel__header">
          <div><h2>{bn ? "সাপোর্ট টিকিট" : "Support tickets"}</h2><p>{bn ? `${ticketTotal}টি টিকিট` : `${ticketTotal} ticket${ticketTotal === 1 ? "" : "s"}`}</p></div>
          <select className="input-field" aria-label={bn ? "টিকিট স্ট্যাটাস" : "Ticket status"} value={ticketStatus} onChange={event => { setTicketStatus(event.target.value); setTicketOffset(0); }}><option value="">{bn ? "সব স্ট্যাটাস" : "All statuses"}</option>{["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "RESOLVED", "CLOSED"].map(status => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select>
        </div>
        {loading ? <div className="empty-state" aria-live="polite">{bn ? "টিকিট লোড হচ্ছে…" : "Loading tickets…"}</div> : tickets.length ? <div className="account-list">{tickets.map(ticket => <article className="account-list__row" key={ticket.id}><div><strong>{ticket.public_id} · {ticket.subject}</strong><span>{ticket.category} · {ticket.priority} · {formatDateTime(ticket.updated_at || ticket.created_at, intlLocale)}{ticket.order_id ? ` · ${bn ? "অর্ডার" : "Order"} #${ticket.order_id}` : ""}</span></div><span className={`admin-status admin-status--${ticket.status.toLowerCase()}`}>{ticket.status.replaceAll("_", " ")}</span><button className="button button--ghost" type="button" onClick={() => void openTicket(ticket)}>{bn ? "কথোপকথন" : "Conversation"}</button></article>)}</div> : <div className="empty-state"><strong>{bn ? "কোনো টিকিট নেই" : "No support tickets"}</strong></div>}
        {ticketTotal > pageSize ? <div className="account-pagination"><button className="button button--ghost" type="button" disabled={ticketOffset === 0 || loading} onClick={() => setTicketOffset(current => Math.max(0, current - pageSize))}>{bn ? "আগের" : "Previous"}</button><span>{ticketOffset + 1}–{Math.min(ticketOffset + pageSize, ticketTotal)} / {ticketTotal}</span><button className="button button--ghost" type="button" disabled={ticketOffset + pageSize >= ticketTotal || loading} onClick={() => setTicketOffset(current => current + pageSize)}>{bn ? "পরের" : "Next"}</button></div> : null}
      </section>

      <section className="account-panel">
        <div className="account-panel__header"><div><h2>{bn ? "Formal disputes" : "Formal disputes"}</h2><p>{bn ? "একটি অর্ডারের জন্য একবারে একটি active dispute রাখা যায়।" : "Only one active dispute is allowed per order."}</p></div><Link href="/account/orders">{bn ? "অর্ডার দেখুন →" : "View orders →"}</Link></div>
        {loading ? <div className="empty-state" aria-live="polite">{bn ? "Dispute লোড হচ্ছে…" : "Loading disputes…"}</div> : disputes.length ? <div className="account-list">{disputes.map(dispute => <article className="account-list__row" key={dispute.id}><div><strong>{dispute.public_id} · {dispute.type.replaceAll("_", " ")}</strong><span>{bn ? "অর্ডার" : "Order"} #{dispute.order_id} · {formatDateTime(dispute.updated_at || dispute.created_at, intlLocale)}</span></div><span className={`admin-status admin-status--${dispute.status.toLowerCase()}`}>{dispute.status.replaceAll("_", " ")}</span><div className="account-inline-actions"><button className="button button--ghost" type="button" onClick={() => void openDispute(dispute)}>{bn ? "দেখুন" : "View"}</button>{activeDispute(dispute.status) ? <button className="button button--ghost button--danger-text" type="button" onClick={() => { setCancelTarget(dispute); setCancelNote(""); }}>{bn ? "বাতিল" : "Cancel"}</button> : null}</div></article>)}</div> : <div className="empty-state"><strong>{bn ? "কোনো dispute নেই" : "No disputes"}</strong><span>{bn ? "সাধারণ প্রশ্নের জন্য আগে support ticket ব্যবহার করুন।" : "Use a support ticket first for general questions."}</span></div>}
        {disputeTotal > pageSize ? <div className="account-pagination"><button className="button button--ghost" type="button" disabled={disputeOffset === 0 || loading} onClick={() => setDisputeOffset(current => Math.max(0, current - pageSize))}>{bn ? "আগের" : "Previous"}</button><span>{disputeOffset + 1}–{Math.min(disputeOffset + pageSize, disputeTotal)} / {disputeTotal}</span><button className="button button--ghost" type="button" disabled={disputeOffset + pageSize >= disputeTotal || loading} onClick={() => setDisputeOffset(current => current + pageSize)}>{bn ? "পরের" : "Next"}</button></div> : null}
      </section>

      <AdminModal open={ticketFormOpen} onClose={() => !saving && setTicketFormOpen(false)} title={bn ? "নতুন সাপোর্ট টিকিট" : "New support ticket"} description={bn ? "Order ID ঐচ্ছিক; payment/shipping সমস্যায় দিলে দ্রুত context পাওয়া যাবে।" : "Order ID is optional and helps staff resolve payment or shipping issues faster."}>
        <form className="admin-modal__form" onSubmit={createTicket}>
          <label><span>{bn ? "বিষয়" : "Subject"}</span><input required minLength={3} maxLength={200} value={ticketForm.subject} onChange={event => setTicketForm(current => ({ ...current, subject: event.target.value }))} /></label>
          <label><span>{bn ? "বিভাগ" : "Category"}</span><select value={ticketForm.category} onChange={event => setTicketForm(current => ({ ...current, category: event.target.value }))}>{["ORDER", "PAYMENT", "SHIPPING", "PRODUCT", "ACCOUNT", "OTHER"].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
          <label><span>{bn ? "অগ্রাধিকার" : "Priority"}</span><select value={ticketForm.priority} onChange={event => setTicketForm(current => ({ ...current, priority: event.target.value }))}>{["LOW", "NORMAL", "HIGH", "URGENT"].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
          <label><span>{bn ? "Order ID (ঐচ্ছিক)" : "Order ID (optional)"}</span><input type="number" min={1} value={ticketForm.order_id} onChange={event => setTicketForm(current => ({ ...current, order_id: event.target.value }))} /></label>
          <label><span>{bn ? "বার্তা" : "Message"}</span><textarea required minLength={3} maxLength={5000} rows={6} value={ticketForm.message} onChange={event => setTicketForm(current => ({ ...current, message: event.target.value }))} /></label>
          {error ? <div className="admin-alert admin-alert--error">{error}</div> : null}
          <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setTicketFormOpen(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving}>{saving ? (bn ? "পাঠানো হচ্ছে…" : "Sending…") : (bn ? "টিকিট খুলুন" : "Open ticket")}</button></div>
        </form>
      </AdminModal>

      <AdminModal open={selectedTicket !== null} onClose={() => !saving && setSelectedTicket(null)} title={selectedTicket?.public_id || (bn ? "সাপোর্ট টিকিট" : "Support ticket")} description={selectedTicket ? `${selectedTicket.subject} · ${selectedTicket.status.replaceAll("_", " ")}` : undefined}>
        {selectedTicket ? <div className="account-case-detail">
          {detailLoading ? <div className="empty-state" aria-live="polite">{bn ? "কথোপকথন লোড হচ্ছে…" : "Loading conversation…"}</div> : <>
            <div className="account-message-list">{selectedTicket.messages?.length ? selectedTicket.messages.map(message => <article className={message.author_role === "customer" ? "account-message account-message--customer" : "account-message account-message--staff"} key={message.id}><div><strong>{message.author_role === "customer" ? (bn ? "আপনি" : "You") : (bn ? "সাপোর্ট টিম" : "Support team")}</strong><time>{formatDateTime(message.created_at, intlLocale)}</time></div><p>{message.body}</p></article>) : <div className="empty-state">{bn ? "কোনো বার্তা নেই।" : "No messages."}</div>}</div>
            {selectedTicket.status !== "CLOSED" ? <form className="admin-modal__form account-reply-form" onSubmit={submitReply}><label><span>{bn ? "উত্তর" : "Reply"}</span><textarea required minLength={1} maxLength={5000} rows={4} value={reply} onChange={event => setReply(event.target.value)} /></label><div className="admin-modal__actions"><button className="admin-button admin-button--primary" disabled={saving || !reply.trim()}>{saving ? (bn ? "পাঠানো হচ্ছে…" : "Sending…") : (bn ? "উত্তর পাঠান" : "Send reply")}</button></div></form> : <div className="account-alert"><span>{bn ? "এই টিকিটটি বন্ধ; নতুন সহায়তার জন্য আরেকটি টিকিট খুলুন।" : "This ticket is closed. Open a new ticket for further help."}</span></div>}
          </>}
        </div> : null}
      </AdminModal>

      <AdminModal open={disputeFormOpen} onClose={() => !saving && setDisputeFormOpen(false)} title={bn ? "Formal dispute খুলুন" : "Open a formal dispute"} description={bn ? "সঠিক order ID এবং চাওয়া সমাধান দিন। জমা দেওয়ার পর case audit trail-এ থাকবে।" : "Provide the correct order and requested resolution. The case is retained in the audit trail."}>
        <form className="admin-modal__form" onSubmit={createDispute}>
          <label><span>{bn ? "Order ID" : "Order ID"}</span><input required type="number" min={1} value={disputeForm.order_id} onChange={event => setDisputeForm(current => ({ ...current, order_id: event.target.value }))} /></label>
          <label><span>{bn ? "ধরন" : "Type"}</span><select value={disputeForm.dispute_type} onChange={event => setDisputeForm(current => ({ ...current, dispute_type: event.target.value }))}>{["PAYMENT", "PRODUCT_QUALITY", "MISSING_ITEM", "DELIVERY", "REFUND", "OTHER"].map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
          <label><span>{bn ? "সমস্যার বিস্তারিত" : "Issue details"}</span><textarea required minLength={10} maxLength={5000} rows={6} value={disputeForm.description} onChange={event => setDisputeForm(current => ({ ...current, description: event.target.value }))} /></label>
          <label><span>{bn ? "চাওয়া সমাধান" : "Requested resolution"}</span><textarea required minLength={3} maxLength={2000} rows={4} value={disputeForm.requested_resolution} onChange={event => setDisputeForm(current => ({ ...current, requested_resolution: event.target.value }))} /></label>
          {error ? <div className="admin-alert admin-alert--error">{error}</div> : null}
          <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setDisputeFormOpen(false)}>{bn ? "ফিরে যান" : "Back"}</button><button className="admin-button admin-button--primary" disabled={saving}>{saving ? (bn ? "জমা হচ্ছে…" : "Submitting…") : (bn ? "Dispute জমা দিন" : "Submit dispute")}</button></div>
        </form>
      </AdminModal>

      <AdminModal open={selectedDispute !== null} onClose={() => !detailLoading && setSelectedDispute(null)} title={selectedDispute?.public_id || "Dispute"} description={selectedDispute ? `${bn ? "অর্ডার" : "Order"} #${selectedDispute.order_id} · ${selectedDispute.status.replaceAll("_", " ")}` : undefined}>
        {selectedDispute ? <div className="account-case-detail">{detailLoading ? <div className="empty-state" aria-live="polite">{bn ? "বিস্তারিত লোড হচ্ছে…" : "Loading details…"}</div> : <>
          <dl className="account-definition-list"><div><dt>{bn ? "ধরন" : "Type"}</dt><dd>{selectedDispute.type.replaceAll("_", " ")}</dd></div><div><dt>{bn ? "তৈরির সময়" : "Created"}</dt><dd>{formatDateTime(selectedDispute.created_at, intlLocale)}</dd></div><div><dt>{bn ? "সিদ্ধান্তের সময়" : "Decision time"}</dt><dd>{formatDateTime(selectedDispute.decided_at, intlLocale)}</dd></div></dl>
          <section><h3>{bn ? "সমস্যা" : "Issue"}</h3><p>{selectedDispute.description}</p></section><section><h3>{bn ? "চাওয়া সমাধান" : "Requested resolution"}</h3><p>{selectedDispute.requested_resolution}</p></section>{selectedDispute.resolution_note ? <section><h3>{bn ? "সিদ্ধান্ত/নোট" : "Decision / note"}</h3><p>{selectedDispute.resolution_note}</p></section> : null}
          {activeDispute(selectedDispute.status) ? <div className="admin-modal__actions"><button className="admin-button admin-button--danger" type="button" onClick={() => { setCancelTarget(selectedDispute); setSelectedDispute(null); setCancelNote(""); }}>{bn ? "Dispute বাতিল করুন" : "Cancel dispute"}</button></div> : null}
        </>}</div> : null}
      </AdminModal>

      <AdminModal open={cancelTarget !== null} onClose={() => !saving && setCancelTarget(null)} title={bn ? "Dispute বাতিল করবেন?" : "Cancel dispute?"} description={bn ? "বাতিলের কারণ audit record-এ সংরক্ষিত হবে।" : "The cancellation reason is retained in the case record."}>
        <form className="admin-modal__form" onSubmit={event => { event.preventDefault(); void cancelDispute(); }}><label><span>{bn ? "বাতিলের কারণ" : "Cancellation reason"}</span><textarea required minLength={3} maxLength={1000} rows={4} value={cancelNote} onChange={event => setCancelNote(event.target.value)} /></label>{error ? <div className="admin-alert admin-alert--error">{error}</div> : null}<div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setCancelTarget(null)}>{bn ? "ফিরে যান" : "Keep dispute"}</button><button className="admin-button admin-button--danger" disabled={saving || cancelNote.trim().length < 3}>{saving ? (bn ? "বাতিল হচ্ছে…" : "Cancelling…") : (bn ? "নিশ্চিত করুন" : "Confirm cancellation")}</button></div></form>
      </AdminModal>
      {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
    </div>
  );
}
