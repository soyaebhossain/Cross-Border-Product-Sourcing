"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import { getAdminUser, updateAdminUser } from "../../../../lib/admin-api";
import type { AdminUserRow } from "../../../../lib/api";
import { formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

type Role = "customer" | "operator" | "admin";

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [user, setUser] = useState<AdminUserRow | null>(null);
  const [role, setRole] = useState<Role>("customer");
  const [active, setActive] = useState(true);
  const [note, setNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getAdminUser(id);
      setUser(result);
      setRole((result.role || "customer") as Role);
      setActive(result.is_active !== false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "ইউজার লোড করা যায়নি।" : "User could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, id]);

  useEffect(() => { void load(); }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateAdminUser(user.id, { role, is_active: active, note: note.trim() });
      setUser(updated);
      setRole((updated.role || role) as Role);
      setActive(updated.is_active !== false);
      setNote("");
      setConfirming(false);
      setToast(bn ? "অ্যাক্সেস পরিবর্তনটি audit log-সহ সংরক্ষিত হয়েছে।" : "Access change saved with an audit record.");
      window.setTimeout(() => setToast(""), 3600);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "অ্যাক্সেস পরিবর্তন করা যায়নি।" : "Access could not be changed."));
      setConfirming(false);
    } finally {
      setSaving(false);
    }
  };

  if (loading && !user) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "ইউজার লোড হচ্ছে…" : "Loading user…"}</div>;
  if (!user) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "ইউজার পাওয়া যায়নি" : "User unavailable"}</strong><span>{error}</span><button type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div></div>;

  const changed = role !== user.role || active !== (user.is_active !== false);
  return <div className="admin-page">
    <header className="admin-page-header">
      <div><Link className="account-back-link" href="/admin/users">← {bn ? "ইউজার তালিকা" : "User list"}</Link><p className="admin-eyebrow">{bn ? "অ্যাক্সেস কন্ট্রোল" : "Access control"}</p><h1>{user.username || user.email || `User #${user.id}`}</h1><p>{user.email || user.phone || `ID #${user.id}`}</p></div>
      <div className="admin-toolbar"><Link className="admin-button admin-button--secondary" href="/admin/roles">{bn ? "রোল নীতি" : "Role policy"}</Link><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></div>
    </header>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "পরিবর্তন ব্যর্থ" : "Change failed"}</strong><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}

    <div className="admin-detail-grid">
      <section className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "অ্যাকাউন্ট তথ্য" : "Account details"}</h2><p>{bn ? "পরিচয় ও ব্যবহারের সারাংশ" : "Identity and usage summary"}</p></div><span className={`admin-status admin-status--${user.is_active === false ? "inactive" : "active"}`}>{user.is_active === false ? "INACTIVE" : "ACTIVE"}</span></div>
        <dl className="account-definition-list">
          <div><dt>{bn ? "ইউজারনেম" : "Username"}</dt><dd>{user.username || "—"}</dd></div>
          <div><dt>Email</dt><dd>{user.email || "—"}</dd></div>
          <div><dt>{bn ? "ফোন" : "Phone"}</dt><dd>{user.phone || "—"}</dd></div>
          <div><dt>{bn ? "বর্তমান রোল" : "Current role"}</dt><dd><span className={`admin-status admin-status--${user.role.toLowerCase()}`}>{user.role}</span></dd></div>
          <div><dt>{bn ? "অর্ডার" : "Orders"}</dt><dd>{user.orders ?? 0}</dd></div>
          <div><dt>{bn ? "সেভড কোট" : "Saved quotes"}</dt><dd>{user.saved_quotes ?? 0}</dd></div>
          <div><dt>{bn ? "যোগ দিয়েছেন" : "Joined"}</dt><dd>{formatDateTime(user.created_at, intlLocale)}</dd></div>
        </dl>
      </section>

      <section className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "রোল ও অ্যাকাউন্ট অবস্থা" : "Role and account state"}</h2><p>{bn ? "এই পরিবর্তন তাৎক্ষণিকভাবে server-side RBAC-এ কার্যকর হবে।" : "Changes take effect immediately in server-side RBAC."}</p></div></div>
        <form className="admin-form-grid" onSubmit={event => { event.preventDefault(); setConfirming(true); }}>
          <label><span>{bn ? "রোল" : "Role"}</span><select value={role} onChange={event => setRole(event.target.value as Role)}><option value="customer">Customer</option><option value="operator">Operator</option><option value="admin">Administrator</option></select></label>
          <label className="admin-checkbox-label"><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} /><span>{bn ? "অ্যাকাউন্ট সক্রিয়" : "Account active"}</span></label>
          <label className="admin-form-grid__wide"><span>{bn ? "আবশ্যিক audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} rows={4} required value={note} onChange={event => setNote(event.target.value)} placeholder={bn ? "কেন এই পরিবর্তন করা হচ্ছে" : "Why this access change is required"} /></label>
          <div className="admin-form-grid__wide admin-detail-actions"><button className="admin-button admin-button--primary" disabled={!changed || note.trim().length < 3}>{bn ? "পরিবর্তন পর্যালোচনা" : "Review access change"}</button></div>
        </form>
      </section>
    </div>

    <AdminModal open={confirming} onClose={() => !saving && setConfirming(false)} title={bn ? "অ্যাক্সেস পরিবর্তন নিশ্চিত করবেন?" : "Confirm access change?"} description={bn ? "ভুল role বা deactivation ব্যবহারকারীর প্রবেশ বন্ধ করতে পারে। Backend শেষ administrator-কে সুরক্ষিত রাখে।" : "A wrong role or deactivation can remove access. The backend protects the last administrator."}>
      <form className="admin-modal__form" onSubmit={submit}>
        <div className="admin-decision-summary"><span>{user.role} → {role}</span><strong>{active ? "ACTIVE" : "INACTIVE"}</strong></div>
        <label><span>{bn ? "Audit note" : "Audit note"}</span><textarea value={note} readOnly rows={3} /></label>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setConfirming(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "নিশ্চিত করুন" : "Confirm")}</button></div>
      </form>
    </AdminModal>
    {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
  </div>;
}
