"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getNotificationPreferences,
  listCustomerNotifications,
  markAllCustomerNotificationsRead,
  markCustomerNotificationRead,
  updateNotificationPreferences,
  type CustomerNotification,
  type NotificationPreferences,
} from "../../../lib/customer-api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

const pageSize = 10;
const preferenceKeys: Array<keyof Omit<NotificationPreferences, "updated_at">> = [
  "order_email", "order_sms", "order_whatsapp", "support_email", "support_sms", "support_whatsapp", "marketing_email",
];

export default function NotificationsPage() {
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [notifications, setNotifications] = useState<CustomerNotification[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextPreferences, result] = await Promise.all([
        getNotificationPreferences(),
        listCustomerNotifications({ unread_only: unreadOnly, limit: pageSize, offset }),
      ]);
      setPreferences(nextPreferences);
      setNotifications(result.items);
      setTotal(result.total);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "নোটিফিকেশন লোড করা যায়নি।" : "Notifications could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, offset, unreadOnly]);

  useEffect(() => { void load(); }, [load]);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  };

  const savePreferences = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!preferences) return;
    setSaving(true);
    setError("");
    try {
      const payload = Object.fromEntries(preferenceKeys.map(key => [key, preferences[key]])) as Partial<NotificationPreferences>;
      setPreferences(await updateNotificationPreferences(payload));
      notify(bn ? "নোটিফিকেশন পছন্দ সংরক্ষিত হয়েছে।" : "Notification preferences saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "পছন্দ সংরক্ষণ করা যায়নি।" : "Preferences could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  const readOne = async (notification: CustomerNotification) => {
    if (notification.read_at) return;
    setWorkingId(notification.id);
    setError("");
    try {
      const updated = await markCustomerNotificationRead(notification.id);
      if (unreadOnly) {
        setNotifications(current => current.filter(item => item.id !== notification.id));
        setTotal(current => Math.max(0, current - 1));
      } else {
        setNotifications(current => current.map(item => item.id === updated.id ? updated : item));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "নোটিফিকেশন আপডেট করা যায়নি।" : "Notification could not be updated."));
    } finally {
      setWorkingId(null);
    }
  };

  const readAll = async () => {
    setWorkingId(-1);
    setError("");
    try {
      const result = await markAllCustomerNotificationsRead();
      notify(bn ? `${result.updated}টি নোটিফিকেশন পড়া হয়েছে।` : `${result.updated} notification${result.updated === 1 ? "" : "s"} marked read.`);
      setOffset(0);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "সব নোটিফিকেশন আপডেট করা যায়নি।" : "Notifications could not be updated."));
    } finally {
      setWorkingId(null);
    }
  };

  const setPreference = (key: keyof Omit<NotificationPreferences, "updated_at">, value: boolean) => {
    setPreferences(current => current ? { ...current, [key]: value } : current);
  };

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div>
          <p className="eyebrow">{bn ? "যোগাযোগ নিয়ন্ত্রণ" : "Communication controls"}</p>
          <h1>{bn ? "নোটিফিকেশন" : "Notifications"}</h1>
          <p>{bn ? "Order/support update-এর channel পছন্দ এবং delivery status এক জায়গায় দেখুন।" : "Manage channels for order and support updates, and review real delivery status."}</p>
        </div>
        <button className="button button--ghost" type="button" disabled={workingId !== null || loading || total === 0} onClick={() => void readAll()}>{bn ? "সব পড়া হয়েছে" : "Mark all read"}</button>
      </header>

      {error ? <div className="account-alert account-alert--danger" role="alert"><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}

      <section className="account-panel">
        <div className="account-panel__header">
          <div>
            <h2>{bn ? "ডেলিভারি পছন্দ" : "Delivery preferences"}</h2>
            <p>{bn ? "চ্যানেল চালু করলে backend provider-এর মাধ্যমে পাঠানোর চেষ্টা করবে; queued/failed/sent ফলাফল নিচে দেখা যাবে।" : "Enabled channels are attempted through the configured provider; queued, failed and sent outcomes appear below."}</p>
          </div>
        </div>
        {preferences ? <form className="account-preference-grid" onSubmit={savePreferences}>
          <fieldset>
            <legend>{bn ? "অর্ডার আপডেট" : "Order updates"}</legend>
            <label><input type="checkbox" checked={preferences.order_email} onChange={event => setPreference("order_email", event.target.checked)} /><span>Email</span></label>
            <label><input type="checkbox" checked={preferences.order_sms} onChange={event => setPreference("order_sms", event.target.checked)} /><span>SMS</span></label>
            <label><input type="checkbox" checked={preferences.order_whatsapp} onChange={event => setPreference("order_whatsapp", event.target.checked)} /><span>WhatsApp</span></label>
          </fieldset>
          <fieldset>
            <legend>{bn ? "সাপোর্ট ও dispute" : "Support and disputes"}</legend>
            <label><input type="checkbox" checked={preferences.support_email} onChange={event => setPreference("support_email", event.target.checked)} /><span>Email</span></label>
            <label><input type="checkbox" checked={preferences.support_sms} onChange={event => setPreference("support_sms", event.target.checked)} /><span>SMS</span></label>
            <label><input type="checkbox" checked={preferences.support_whatsapp} onChange={event => setPreference("support_whatsapp", event.target.checked)} /><span>WhatsApp</span></label>
          </fieldset>
          <fieldset>
            <legend>{bn ? "অন্যান্য" : "Other"}</legend>
            <label><input type="checkbox" checked={preferences.marketing_email} onChange={event => setPreference("marketing_email", event.target.checked)} /><span>{bn ? "Marketing email" : "Marketing email"}</span></label>
          </fieldset>
          <div className="account-form-actions"><button className="button button--primary" disabled={saving || loading}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "পছন্দ সংরক্ষণ" : "Save preferences")}</button>{preferences.updated_at ? <small>{bn ? "সর্বশেষ সংরক্ষণ" : "Last saved"}: {formatDateTime(preferences.updated_at, intlLocale)}</small> : null}</div>
        </form> : <div className="empty-state" aria-live="polite">{loading ? (bn ? "পছন্দ লোড হচ্ছে…" : "Loading preferences…") : (bn ? "পছন্দ পাওয়া যায়নি।" : "Preferences are unavailable.")}</div>}
      </section>

      <section className="account-panel">
        <div className="account-panel__header">
          <div><h2>{bn ? "ইনবক্স" : "Inbox"}</h2><p>{bn ? `${total}টি ${unreadOnly ? "অপঠিত" : ""} নোটিফিকেশন` : `${total} ${unreadOnly ? "unread " : ""}notification${total === 1 ? "" : "s"}`}</p></div>
          <label className="account-toggle"><input type="checkbox" checked={unreadOnly} onChange={event => { setUnreadOnly(event.target.checked); setOffset(0); }} /><span>{bn ? "শুধু অপঠিত" : "Unread only"}</span></label>
        </div>
        {loading ? <div className="empty-state" aria-live="polite">{bn ? "নোটিফিকেশন লোড হচ্ছে…" : "Loading notifications…"}</div> : notifications.length ? <div className="account-notification-list">
          {notifications.map(notification => <article className={notification.read_at ? "account-notification" : "account-notification account-notification--unread"} key={notification.id}>
            <div className="account-notification__header">
              <div><span className={`admin-status admin-status--${notification.read_at ? "neutral" : "pending"}`}>{notification.category}</span><h3>{notification.title}</h3></div>
              <time>{formatDateTime(notification.created_at, intlLocale)}</time>
            </div>
            <p>{notification.body}</p>
            {notification.order_id ? <small>{bn ? "অর্ডার" : "Order"} #{notification.order_id}</small> : null}
            {notification.deliveries.length ? <div className="account-delivery-list">{notification.deliveries.map(delivery => <span key={delivery.id} title={delivery.error_code || undefined}><strong>{delivery.channel}</strong> · {delivery.status}{delivery.destination_masked ? ` · ${delivery.destination_masked}` : ""}{delivery.attempts ? ` · ${bn ? "চেষ্টা" : "attempts"} ${delivery.attempts}` : ""}{delivery.error_code ? ` · ${delivery.error_code}` : ""}</span>)}</div> : <div className="account-delivery-list"><span>{bn ? "কোনো external channel queue হয়নি।" : "No external channel was queued."}</span></div>}
            {!notification.read_at ? <button className="button button--ghost" type="button" disabled={workingId === notification.id} onClick={() => void readOne(notification)}>{workingId === notification.id ? (bn ? "আপডেট হচ্ছে…" : "Updating…") : (bn ? "পড়া হয়েছে" : "Mark read")}</button> : null}
          </article>)}
        </div> : <div className="empty-state"><strong>{unreadOnly ? (bn ? "কোনো অপঠিত নোটিফিকেশন নেই" : "No unread notifications") : (bn ? "এখনো কোনো নোটিফিকেশন নেই" : "No notifications yet")}</strong></div>}
        {total > pageSize ? <div className="account-pagination">
          <button className="button button--ghost" type="button" disabled={offset === 0 || loading} onClick={() => setOffset(current => Math.max(0, current - pageSize))}>{bn ? "আগের" : "Previous"}</button>
          <span>{offset + 1}–{Math.min(offset + pageSize, total)} / {total}</span>
          <button className="button button--ghost" type="button" disabled={offset + pageSize >= total || loading} onClick={() => setOffset(current => current + pageSize)}>{bn ? "পরের" : "Next"}</button>
        </div> : null}
      </section>
      {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
    </div>
  );
}
