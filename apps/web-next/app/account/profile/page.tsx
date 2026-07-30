"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import {
  createCustomerAddress,
  deleteCustomerAddress,
  getCustomerProfile,
  listCustomerAddresses,
  updateCustomerAddress,
  updateCustomerProfile,
  type AddressPayload,
  type CustomerAddress,
  type CustomerProfile,
} from "../../../lib/customer-api";
import { useLocale } from "../../../lib/locale-context";

const blankAddress: AddressPayload = {
  label: "", recipient_name: "", company_name: "", line1: "", line2: "", city: "", region: "", postal_code: "", country_code: "BD", phone: "", is_default_shipping: false, is_default_billing: false,
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [fields, setFields] = useState({ full_name: "", company_name: "", company_registration_number: "", tax_identifier: "", preferred_language: "en" as "en" | "bn", preferred_currency: "BDT", timezone: "Asia/Dhaka" });
  const [addressTarget, setAddressTarget] = useState<CustomerAddress | "new" | null>(null);
  const [address, setAddress] = useState<AddressPayload>(blankAddress);
  const [deleteTarget, setDeleteTarget] = useState<CustomerAddress | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale } = useLocale();
  const bn = locale === "bn";

  const applyProfile = (value: CustomerProfile) => {
    setProfile(value);
    setFields({
      full_name: value.full_name || "",
      company_name: value.company.name || "",
      company_registration_number: value.company.registration_number || "",
      tax_identifier: value.company.tax_identifier || "",
      preferred_language: value.preferences.language || "en",
      preferred_currency: value.preferences.currency || "BDT",
      timezone: value.preferences.timezone || "Asia/Dhaka",
    });
  };
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [nextProfile, nextAddresses] = await Promise.all([getCustomerProfile(), listCustomerAddresses()]);
      applyProfile(nextProfile); setAddresses(nextAddresses);
    } catch (reason) { setError(reason instanceof Error ? reason.message : (bn ? "প্রোফাইল লোড করা যায়নি।" : "Profile could not be loaded.")); }
    finally { setLoading(false); }
  }, [bn]);
  useEffect(() => { void load(); }, [load]);

  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 3500); };
  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      applyProfile(await updateCustomerProfile({
        full_name: fields.full_name.trim() || null,
        company_name: fields.company_name.trim() || null,
        company_registration_number: fields.company_registration_number.trim() || null,
        tax_identifier: fields.tax_identifier.trim() || null,
        preferred_language: fields.preferred_language,
        preferred_currency: fields.preferred_currency.trim().toUpperCase(),
        timezone: fields.timezone.trim(),
      }));
      notify(bn ? "প্রোফাইল সংরক্ষিত হয়েছে।" : "Profile saved.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : (bn ? "প্রোফাইল সংরক্ষণ করা যায়নি।" : "Profile could not be saved.")); }
    finally { setSaving(false); }
  };
  const openNew = () => { setAddressTarget("new"); setAddress({ ...blankAddress }); setError(""); };
  const openEdit = (item: CustomerAddress) => {
    setAddressTarget(item);
    setAddress({ label: item.label, recipient_name: item.recipient_name, company_name: item.company_name || "", line1: item.line1, line2: item.line2 || "", city: item.city, region: item.region || "", postal_code: item.postal_code || "", country_code: item.country_code, phone: item.phone, is_default_shipping: item.is_default_shipping, is_default_billing: item.is_default_billing });
    setError("");
  };
  const saveAddress = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const payload = { ...address, label: address.label.trim(), recipient_name: address.recipient_name.trim(), company_name: address.company_name?.trim() || null, line1: address.line1.trim(), line2: address.line2?.trim() || null, city: address.city.trim(), region: address.region?.trim() || null, postal_code: address.postal_code?.trim() || null, country_code: address.country_code.trim().toUpperCase(), phone: address.phone.trim() };
      if (addressTarget === "new") await createCustomerAddress(payload);
      else if (addressTarget) await updateCustomerAddress(addressTarget.id, payload);
      setAddressTarget(null); notify(bn ? "ঠিকানা সংরক্ষিত হয়েছে।" : "Address saved."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : (bn ? "ঠিকানা সংরক্ষণ করা যায়নি।" : "Address could not be saved.")); }
    finally { setSaving(false); }
  };
  const removeAddress = async () => {
    if (!deleteTarget) return;
    setSaving(true); setError("");
    try { await deleteCustomerAddress(deleteTarget.id); setDeleteTarget(null); notify(bn ? "ঠিকানাটি সরানো হয়েছে।" : "Address removed."); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (bn ? "ঠিকানা সরানো যায়নি।" : "Address could not be removed.")); }
    finally { setSaving(false); }
  };

  if (loading && !profile) return <div className="empty-state" aria-live="polite">{bn ? "প্রোফাইল লোড হচ্ছে…" : "Loading profile…"}</div>;
  if (!profile) return <div className="empty-state" role="alert"><strong>{error || (bn ? "প্রোফাইল পাওয়া যায়নি।" : "Profile not found.")}</strong><button className="button button--ghost" type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div>;

  return <div className="account-page">
    <header className="account-page-header"><div><p className="eyebrow">{bn ? "পরিচয় ও ডেলিভারি" : "Identity and delivery"}</p><h1>{bn ? "প্রোফাইল ও ঠিকানা" : "Profile and addresses"}</h1><p>{bn ? "Company, locale এবং shipping/billing address নিরাপদ account API-তে সংরক্ষণ করুন।" : "Save company, locale and shipping or billing addresses through the secure account API."}</p></div><button className="button button--primary" type="button" onClick={openNew}>{bn ? "ঠিকানা যোগ করুন" : "Add address"}</button></header>
    {error ? <div className="account-alert account-alert--danger" role="alert"><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}

    <section className="account-panel">
      <div className="account-panel__header"><div><h2>{bn ? "ব্যক্তি ও কোম্পানি" : "Person and company"}</h2><p>{profile.username} · {profile.email || profile.phone}</p></div></div>
      <form className="account-profile-form" onSubmit={saveProfile}>
        <label><span>{bn ? "পূর্ণ নাম" : "Full name"}</span><input minLength={2} maxLength={200} value={fields.full_name} onChange={event => setFields(current => ({ ...current, full_name: event.target.value }))} /></label>
        <label><span>{bn ? "কোম্পানির নাম" : "Company name"}</span><input maxLength={200} value={fields.company_name} onChange={event => setFields(current => ({ ...current, company_name: event.target.value }))} /></label>
        <label><span>{bn ? "রেজিস্ট্রেশন নম্বর" : "Registration number"}</span><input maxLength={120} value={fields.company_registration_number} onChange={event => setFields(current => ({ ...current, company_registration_number: event.target.value }))} /></label>
        <label><span>{bn ? "Tax identifier" : "Tax identifier"}</span><input maxLength={120} value={fields.tax_identifier} onChange={event => setFields(current => ({ ...current, tax_identifier: event.target.value }))} /></label>
        <label><span>{bn ? "ভাষা" : "Language"}</span><select value={fields.preferred_language} onChange={event => setFields(current => ({ ...current, preferred_language: event.target.value as "en" | "bn" }))}><option value="en">English</option><option value="bn">বাংলা</option></select></label>
        <label><span>{bn ? "মুদ্রা" : "Currency"}</span><input minLength={3} maxLength={10} pattern="[A-Za-z]+" value={fields.preferred_currency} onChange={event => setFields(current => ({ ...current, preferred_currency: event.target.value }))} required /></label>
        <label><span>{bn ? "Timezone (IANA)" : "Timezone (IANA)"}</span><input value={fields.timezone} maxLength={80} placeholder="Asia/Dhaka" onChange={event => setFields(current => ({ ...current, timezone: event.target.value }))} required /></label>
        <div className="account-profile-form__wide account-form-actions"><button className="button button--primary" disabled={saving}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "প্রোফাইল সংরক্ষণ" : "Save profile")}</button></div>
      </form>
    </section>

    <section className="account-panel">
      <div className="account-panel__header"><div><h2>{bn ? "ঠিকানা বই" : "Address book"}</h2><p>{bn ? "Default shipping ও billing address checkout/invoice snapshot-এ ব্যবহৃত হয়।" : "Default shipping and billing addresses are used for checkout and invoice snapshots."}</p></div></div>
      {addresses.length ? <div className="account-address-grid">{addresses.map(item => <article key={item.id} className="account-address-card"><div><strong>{item.label}</strong><span>{item.is_default_shipping ? (bn ? "Shipping" : "Shipping") : null}{item.is_default_shipping && item.is_default_billing ? " · " : null}{item.is_default_billing ? (bn ? "Billing" : "Billing") : null}</span></div><p>{item.recipient_name}{item.company_name ? ` · ${item.company_name}` : ""}<br />{item.line1}{item.line2 ? `, ${item.line2}` : ""}<br />{item.city}{item.region ? `, ${item.region}` : ""} {item.postal_code || ""} · {item.country_code}<br />{item.phone}</p><div><button className="button button--ghost" type="button" onClick={() => openEdit(item)}>{bn ? "সম্পাদনা" : "Edit"}</button><button className="button button--ghost button--danger-text" type="button" onClick={() => setDeleteTarget(item)}>{bn ? "সরান" : "Remove"}</button></div></article>)}</div> : <div className="empty-state"><strong>{bn ? "কোনো ঠিকানা নেই" : "No addresses yet"}</strong><span>{bn ? "প্রথম ঠিকানাটি shipping ও billing default হবে।" : "Your first address becomes the shipping and billing default."}</span></div>}
    </section>

    <AdminModal open={addressTarget !== null} onClose={() => !saving && setAddressTarget(null)} title={addressTarget === "new" ? (bn ? "ঠিকানা যোগ করুন" : "Add address") : (bn ? "ঠিকানা সম্পাদনা" : "Edit address")} description={bn ? "Country code দুই অক্ষরের ISO code দিন, যেমন BD।" : "Use a two-letter ISO country code, such as BD."}>
      <form className="admin-modal__form" onSubmit={saveAddress}>
        <label><span>{bn ? "লেবেল" : "Label"}</span><input required maxLength={80} value={address.label} onChange={event => setAddress(current => ({ ...current, label: event.target.value }))} placeholder="Office / Home" /></label>
        <label><span>{bn ? "প্রাপকের নাম" : "Recipient name"}</span><input required minLength={2} maxLength={200} value={address.recipient_name} onChange={event => setAddress(current => ({ ...current, recipient_name: event.target.value }))} /></label>
        <label><span>{bn ? "কোম্পানি" : "Company"}</span><input maxLength={200} value={address.company_name || ""} onChange={event => setAddress(current => ({ ...current, company_name: event.target.value }))} /></label>
        <label><span>{bn ? "ঠিকানা ১" : "Address line 1"}</span><input required minLength={3} maxLength={250} value={address.line1} onChange={event => setAddress(current => ({ ...current, line1: event.target.value }))} /></label>
        <label><span>{bn ? "ঠিকানা ২" : "Address line 2"}</span><input maxLength={250} value={address.line2 || ""} onChange={event => setAddress(current => ({ ...current, line2: event.target.value }))} /></label>
        <label><span>{bn ? "শহর" : "City"}</span><input required minLength={2} maxLength={120} value={address.city} onChange={event => setAddress(current => ({ ...current, city: event.target.value }))} /></label>
        <label><span>{bn ? "অঞ্চল" : "Region"}</span><input maxLength={120} value={address.region || ""} onChange={event => setAddress(current => ({ ...current, region: event.target.value }))} /></label>
        <label><span>{bn ? "Postal code" : "Postal code"}</span><input maxLength={40} value={address.postal_code || ""} onChange={event => setAddress(current => ({ ...current, postal_code: event.target.value }))} /></label>
        <label><span>{bn ? "দেশের code" : "Country code"}</span><input required pattern="[A-Za-z]{2}" minLength={2} maxLength={2} value={address.country_code} onChange={event => setAddress(current => ({ ...current, country_code: event.target.value }))} /></label>
        <label><span>{bn ? "ফোন" : "Phone"}</span><input required minLength={5} maxLength={40} value={address.phone} onChange={event => setAddress(current => ({ ...current, phone: event.target.value }))} /></label>
        <label className="admin-checkbox-label"><input type="checkbox" checked={address.is_default_shipping} onChange={event => setAddress(current => ({ ...current, is_default_shipping: event.target.checked }))} /><span>{bn ? "Default shipping" : "Default shipping"}</span></label>
        <label className="admin-checkbox-label"><input type="checkbox" checked={address.is_default_billing} onChange={event => setAddress(current => ({ ...current, is_default_billing: event.target.checked }))} /><span>{bn ? "Default billing" : "Default billing"}</span></label>
        {error ? <div className="admin-alert admin-alert--error">{error}</div> : null}
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setAddressTarget(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div>
      </form>
    </AdminModal>
    <AdminModal open={deleteTarget !== null} onClose={() => !saving && setDeleteTarget(null)} title={bn ? "ঠিকানাটি সরাবেন?" : "Remove address?"} description={bn ? "Default address সরালে অন্য address স্বয়ংক্রিয়ভাবে default হতে পারে।" : "Removing a default address may automatically promote another address."}><div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setDeleteTarget(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--danger" type="button" disabled={saving} onClick={() => void removeAddress()}>{bn ? "সরান" : "Remove"}</button></div></AdminModal>
    {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
  </div>;
}
