"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { createOrder, getSavedQuote, type SavedQuote } from "../../../../../lib/api";
import {
  listCustomerAddresses,
  type CustomerAddress,
} from "../../../../../lib/customer-api";
import { formatBdt, formatDateTime } from "../../../../../lib/format";
import { useLocale } from "../../../../../lib/locale-context";

export default function CreateOrderFromQuotePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [quote, setQuote] = useState<SavedQuote | null>(null);
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [channel, setChannel] = useState("bKash");
  const [trxId, setTrxId] = useState("");
  const [screenshotUrl, setScreenshotUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idempotencyKey = useRef("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => {
    const storageKey = `sourceai-order-idempotency-${params.id}`;
    const existingKey = window.sessionStorage.getItem(storageKey);
    const generatedKey = `quote-${params.id}-${crypto.randomUUID()}`;
    idempotencyKey.current = existingKey || generatedKey;
    if (!existingKey) window.sessionStorage.setItem(storageKey, generatedKey);
    Promise.all([getSavedQuote(params.id), listCustomerAddresses()])
      .then(([savedQuote, customerAddresses]) => {
        setQuote(savedQuote);
        setAddresses(customerAddresses);
      })
      .catch(() => setError(bn ? "সেভড কোট লোড করা যায়নি। সাইন ইন করে আবার চেষ্টা করুন।" : "This saved quote could not be loaded. Please sign in and try again."))
      .finally(() => setLoading(false));
  }, [params.id, bn]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!quote || !trxId.trim()) {
      setError(bn ? "অর্ডার করতে payment transaction ID দিন।" : "Enter your payment transaction ID to place the order.");
      return;
    }
    const defaultShipping = addresses.find((item) => item.is_default_shipping);
    const defaultBilling = addresses.find((item) => item.is_default_billing);
    if (!defaultShipping || !defaultBilling) {
      setError(bn ? "অর্ডারের আগে ডিফল্ট শিপিং ও বিলিং ঠিকানা যোগ করুন।" : "Add default shipping and billing addresses before placing the order.");
      return;
    }
    if ((quote.expires_at && new Date(quote.expires_at).getTime() < Date.now()) || quote.order_ids?.length) {
      setError(quote.order_ids?.length ? (bn ? "এই কোট থেকে ইতিমধ্যে একটি অর্ডার তৈরি হয়েছে।" : "An order has already been created from this quote.") : (bn ? "কোটের মেয়াদ শেষ হয়েছে; নতুন কোট নিন।" : "This quote has expired; request a new quote."));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await createOrder({
        variant_id: quote.variant_id,
        country: quote.country_id,
        mode: quote.mode,
        qty: quote.qty,
        delivery_type: quote.delivery_type || "DOOR",
        saved_quote_id: quote.id,
        idempotency_key: idempotencyKey.current,
        trx_id: trxId.trim(),
        channel,
        screenshot_url: screenshotUrl.trim() || undefined,
      });
      router.push(`/account/orders/${result.order_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "অর্ডার তৈরি করা যায়নি। Transaction ID, quote expiry এবং sign-in যাচাই করুন।" : "Order could not be created. Check the transaction ID, quote expiry and sign-in."));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="empty-state" aria-live="polite">{bn ? "Checkout লোড হচ্ছে…" : "Loading order checkout…"}</div>;
  if (!quote) return <div className="empty-state" role="alert">{error || (bn ? "কোট পাওয়া যায়নি।" : "Quote not found.")}</div>;

  const breakdown = quote.response?.breakdown;
  const expired = Boolean(quote.expires_at && new Date(quote.expires_at).getTime() < Date.now());
  const ordered = Boolean(quote.order_ids?.length);
  const defaultShipping = addresses.find((item) => item.is_default_shipping);
  const defaultBilling = addresses.find((item) => item.is_default_billing);
  const addressReady = Boolean(defaultShipping && defaultBilling);
  return (
      <section className="account-page">
        <div className="section__header">
          <div><p className="eyebrow">{bn ? "অর্ডার checkout" : "Order checkout"}</p><h1>{bn ? "সোর্সিং অর্ডার নিশ্চিত করুন" : "Confirm sourcing order"}</h1><p>{bn ? `কোট #${quote.id} · মেয়াদ ${formatDateTime(quote.expires_at, intlLocale)}` : `Quote #${quote.id} · expires ${formatDateTime(quote.expires_at, intlLocale)}`}</p></div>
        </div>
        {expired || ordered ? <div className="account-alert account-alert--danger" role="alert"><strong>{ordered ? (bn ? "এই কোট থেকে অর্ডার তৈরি হয়েছে" : "This quote has already been ordered") : (bn ? "এই কোটের মেয়াদ শেষ" : "This quote has expired")}</strong><span>{ordered ? `${bn ? "অর্ডার" : "Order"} #${quote.order_ids?.join(", #")}` : (bn ? "সঠিক মূল্য পেতে নতুন কোট নিন।" : "Request a new quote to get a valid price.")}</span></div> : null}
        <div className="quote-summary">
          <div><strong>{bn ? "পণ্য" : "Product"}</strong><span>{quote.product_name}</span></div>
          <div><strong>{bn ? "ভ্যারিয়েন্ট / পরিমাণ" : "Variant / quantity"}</strong><span>{quote.variant_name} · {new Intl.NumberFormat(intlLocale).format(quote.qty)}</span></div>
          <div><strong>{bn ? "সোর্স" : "Source"}</strong><span>{quote.country_id} · {quote.mode}</span></div>
          <div><strong>{bn ? "মোট locked মূল্য" : "Locked total"}</strong><span>{formatBdt(breakdown?.total_bdt, intlLocale)}</span></div>
          <div><strong>{bn ? "প্রয়োজনীয় অগ্রিম" : "Advance required"}</strong><span>{formatBdt(breakdown?.advance_bdt, intlLocale)}</span></div>
          <div><strong>{bn ? "বাকি" : "Remaining"}</strong><span>{formatBdt(breakdown?.remaining_bdt, intlLocale)}</span></div>
        </div>
        <div className={`account-alert ${addressReady ? "account-alert--success" : "account-alert--danger"}`} role={addressReady ? "status" : "alert"}>
          <strong>{addressReady ? (bn ? "ডেলিভারি ঠিকানা প্রস্তুত" : "Delivery addresses ready") : (bn ? "ডেলিভারি ঠিকানা প্রয়োজন" : "Delivery addresses required")}</strong>
          {addressReady ? (
            <span>
              {bn ? "শিপিং" : "Shipping"}: {defaultShipping?.label} · {defaultShipping?.line1}, {defaultShipping?.city}
              {defaultBilling?.id !== defaultShipping?.id ? ` · ${bn ? "বিলিং" : "Billing"}: ${defaultBilling?.label}` : ` · ${bn ? "শিপিং ও বিলিং উভয়ের জন্য" : "also used for billing"}`}
            </span>
          ) : (
            <span>{bn ? "পেমেন্ট রেফারেন্স দেওয়ার আগে প্রোফাইলে একটি ডিফল্ট শিপিং ও বিলিং ঠিকানা সেট করুন।" : "Set default shipping and billing addresses in your profile before submitting payment."} <Link href="/account/profile">{bn ? "ঠিকানা যোগ করুন →" : "Add addresses →"}</Link></span>
          )}
        </div>
        <form className="form-card" onSubmit={submit}>
          <p className="form-note">{bn ? "কোটের অগ্রিম পরিশোধ করে payment reference দিন। Admin যাচাই না করা পর্যন্ত অর্ডার pending থাকবে।" : "Pay the quoted advance, then submit the payment reference. The order remains pending until an admin verifies it."}</p>
          <div className="form-grid">
            <div className="form-field">
              <label>{bn ? "পেমেন্ট চ্যানেল" : "Payment channel"}</label>
              <select className="input-field" value={channel} onChange={(event) => setChannel(event.target.value)}>
                <option value="bKash">bKash</option>
                <option value="Nagad">Nagad</option>
                <option value="Rocket">Rocket</option>
                <option value="Bank">{bn ? "ব্যাংক ট্রান্সফার" : "Bank transfer"}</option>
              </select>
            </div>
            <div className="form-field">
              <label>Transaction ID</label>
              <input className="input-field" required minLength={3} maxLength={80} value={trxId} onChange={(event) => setTrxId(event.target.value)} placeholder={bn ? "পেমেন্ট transaction ID" : "Enter payment transaction ID"} />
            </div>
            <div className="form-field">
              <label>{bn ? "পেমেন্ট screenshot URL (ঐচ্ছিক)" : "Payment screenshot URL (optional)"}</label>
              <input className="input-field" type="url" value={screenshotUrl} onChange={(event) => setScreenshotUrl(event.target.value)} placeholder="https://…" />
              <small>{bn ? "বর্তমান API file upload গ্রহণ করে না—শুধু নিরাপদ HTTPS URL।" : "The current API accepts a secure HTTPS URL, not a direct file upload."}</small>
            </div>
          </div>
          <div className="form-actions">
            <button className="button button--primary" type="submit" disabled={submitting || expired || ordered || !addressReady}>{submitting ? (bn ? "অর্ডার হচ্ছে…" : "Placing order…") : (bn ? "নিশ্চিত করে অর্ডার করুন" : "Confirm and place order")}</button>
            {error ? <div className="form-error" role="alert">{error}</div> : null}
          </div>
        </form>
      </section>
  );
}
