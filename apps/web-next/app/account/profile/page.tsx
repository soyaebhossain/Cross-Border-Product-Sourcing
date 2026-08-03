"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import { AppIcon } from "../../../components/app-icon";
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
import styles from "./profile.module.css";

const blankAddress: AddressPayload = {
  label: "",
  recipient_name: "",
  company_name: "",
  line1: "",
  line2: "",
  city: "",
  region: "",
  postal_code: "",
  country_code: "BD",
  phone: "",
  is_default_shipping: false,
  is_default_billing: false,
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [fields, setFields] = useState({
    full_name: "",
    company_name: "",
    company_registration_number: "",
    tax_identifier: "",
    preferred_language: "en" as "en" | "bn",
    preferred_currency: "BDT",
    timezone: "Asia/Dhaka",
  });
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
    setLoading(true);
    setError("");
    try {
      const [nextProfile, nextAddresses] = await Promise.all([
        getCustomerProfile(),
        listCustomerAddresses(),
      ]);
      applyProfile(nextProfile);
      setAddresses(nextAddresses);
    } catch (reason) {
      setError(reason instanceof Error
        ? reason.message
        : (bn ? "প্রোফাইল লোড করা যায়নি।" : "Profile could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn]);

  useEffect(() => {
    void load();
  }, [load]);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  };

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
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
    } catch (reason) {
      setError(reason instanceof Error
        ? reason.message
        : (bn ? "প্রোফাইল সংরক্ষণ করা যায়নি।" : "Profile could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  const openNew = () => {
    setAddressTarget("new");
    setAddress({ ...blankAddress });
    setError("");
  };

  const openEdit = (item: CustomerAddress) => {
    setAddressTarget(item);
    setAddress({
      label: item.label,
      recipient_name: item.recipient_name,
      company_name: item.company_name || "",
      line1: item.line1,
      line2: item.line2 || "",
      city: item.city,
      region: item.region || "",
      postal_code: item.postal_code || "",
      country_code: item.country_code,
      phone: item.phone,
      is_default_shipping: item.is_default_shipping,
      is_default_billing: item.is_default_billing,
    });
    setError("");
  };

  const closeAddressDialog = () => {
    if (saving) return;
    setAddressTarget(null);
    setError("");
  };

  const closeDeleteDialog = () => {
    if (saving) return;
    setDeleteTarget(null);
    setError("");
  };

  const saveAddress = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...address,
        label: address.label.trim(),
        recipient_name: address.recipient_name.trim(),
        company_name: address.company_name?.trim() || null,
        line1: address.line1.trim(),
        line2: address.line2?.trim() || null,
        city: address.city.trim(),
        region: address.region?.trim() || null,
        postal_code: address.postal_code?.trim() || null,
        country_code: address.country_code.trim().toUpperCase(),
        phone: address.phone.trim(),
      };
      if (addressTarget === "new") await createCustomerAddress(payload);
      else if (addressTarget) await updateCustomerAddress(addressTarget.id, payload);
      setAddressTarget(null);
      notify(bn ? "ঠিকানা সংরক্ষিত হয়েছে।" : "Address saved.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error
        ? reason.message
        : (bn ? "ঠিকানা সংরক্ষণ করা যায়নি।" : "Address could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  const removeAddress = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    setError("");
    try {
      await deleteCustomerAddress(deleteTarget.id);
      setDeleteTarget(null);
      notify(bn ? "ঠিকানাটি সরানো হয়েছে।" : "Address removed.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error
        ? reason.message
        : (bn ? "ঠিকানা সরানো যায়নি।" : "Address could not be removed."));
    } finally {
      setSaving(false);
    }
  };

  if (loading && !profile) {
    return <div className="empty-state" aria-live="polite">{bn ? "প্রোফাইল লোড হচ্ছে…" : "Loading profile…"}</div>;
  }

  if (!profile) {
    return (
      <div className="empty-state" role="alert">
        <strong>{error || (bn ? "প্রোফাইল পাওয়া যায়নি।" : "Profile not found.")}</strong>
        <button className="button button--ghost" type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button>
      </div>
    );
  }

  const identity = profile.full_name || profile.username || profile.email || profile.phone || `User ${profile.user_id}`;
  const identityInitial = identity.trim().slice(0, 1).toUpperCase() || "U";
  const optional = bn ? "ঐচ্ছিক" : "Optional";

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div>
          <p className="eyebrow">{bn ? "পরিচয় ও ডেলিভারি" : "Identity and delivery"}</p>
          <h1>{bn ? "প্রোফাইল ও ঠিকানা" : "Profile and addresses"}</h1>
          <p>{bn ? "কোম্পানি, ভাষা এবং shipping/billing ঠিকানা নিরাপদে পরিচালনা করুন।" : "Manage your company, regional preferences, and shipping or billing addresses securely."}</p>
        </div>
        <button className="button button--primary" type="button" onClick={openNew}>
          <span className={styles.buttonIcon} aria-hidden>+</span>
          {bn ? "ঠিকানা যোগ করুন" : "Add address"}
        </button>
      </header>

      {error && addressTarget === null && deleteTarget === null ? (
        <div className="account-alert account-alert--danger" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button>
        </div>
      ) : null}

      <section className={`account-panel ${styles.profilePanel}`} aria-labelledby="profile-details-heading">
        <div className={styles.identitySummary}>
          <div className={styles.identityAvatar} aria-hidden>{identityInitial}</div>
          <div className={styles.identityCopy}>
            <h2 id="profile-details-heading">{bn ? "ব্যক্তি ও কোম্পানি" : "Person and company"}</h2>
            <p>{profile.username} · {profile.email || profile.phone}</p>
          </div>
          <span className={styles.accountBadge}><AppIcon name="shield" size={12} />{bn ? "কাস্টমার প্রোফাইল" : "Customer profile"}</span>
        </div>

        <form className={`account-profile-form ${styles.profileForm}`} onSubmit={saveProfile} aria-busy={saving}>
          <section className={styles.formSection} aria-labelledby="personal-details-heading">
            <div className={styles.sectionHeading}>
              <span className={styles.sectionIcon}><AppIcon name="user" size={16} /></span>
              <div>
                <h3 id="personal-details-heading">{bn ? "ব্যক্তিগত তথ্য" : "Personal details"}</h3>
                <p>{bn ? "Invoice ও delivery যোগাযোগের জন্য ব্যবহৃত পরিচয়।" : "Identity used for invoice and delivery communication."}</p>
              </div>
            </div>
            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "পূর্ণ নাম" : "Full name"}<small className={styles.optional}>{optional}</small></span>
                <input className={styles.control} name="full_name" autoComplete="name" minLength={2} maxLength={200} placeholder={bn ? "আপনার পূর্ণ নাম" : "Your full name"} value={fields.full_name} onChange={event => setFields(current => ({ ...current, full_name: event.target.value }))} />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "কোম্পানির নাম" : "Company name"}<small className={styles.optional}>{optional}</small></span>
                <input className={styles.control} name="company_name" autoComplete="organization" maxLength={200} placeholder={bn ? "কোম্পানি বা ব্যবসার নাম" : "Company or business name"} value={fields.company_name} onChange={event => setFields(current => ({ ...current, company_name: event.target.value }))} />
              </label>
            </div>
          </section>

          <section className={styles.formSection} aria-labelledby="business-details-heading">
            <div className={styles.sectionHeading}>
              <span className={styles.sectionIcon}><AppIcon name="orders" size={16} /></span>
              <div>
                <h3 id="business-details-heading">{bn ? "ব্যবসার পরিচয়" : "Business identity"}</h3>
                <p>{bn ? "Commercial invoice ও compliance record-এর ঐচ্ছিক তথ্য।" : "Optional details for commercial invoices and compliance records."}</p>
              </div>
            </div>
            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "রেজিস্ট্রেশন নম্বর" : "Registration number"}<small className={styles.optional}>{optional}</small></span>
                <input className={styles.control} name="company_registration_number" maxLength={120} spellCheck={false} placeholder="RJSC / Trade license" value={fields.company_registration_number} onChange={event => setFields(current => ({ ...current, company_registration_number: event.target.value }))} />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "ট্যাক্স আইডেন্টিফায়ার" : "Tax identifier"}<small className={styles.optional}>{optional}</small></span>
                <input className={styles.control} name="tax_identifier" maxLength={120} spellCheck={false} placeholder="TIN / VAT / Tax ID" value={fields.tax_identifier} onChange={event => setFields(current => ({ ...current, tax_identifier: event.target.value }))} />
              </label>
            </div>
          </section>

          <section className={styles.formSection} aria-labelledby="regional-preferences-heading">
            <div className={styles.sectionHeading}>
              <span className={styles.sectionIcon}><AppIcon name="globe" size={16} /></span>
              <div>
                <h3 id="regional-preferences-heading">{bn ? "আঞ্চলিক পছন্দ" : "Regional preferences"}</h3>
                <p>{bn ? "ভাষা, মুদ্রা ও সময় আপনার account জুড়ে একইভাবে দেখাবে।" : "Language, currency, and time display consistently across your account."}</p>
              </div>
            </div>
            <div className={styles.preferenceGrid}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "ভাষা" : "Language"}</span>
                <select className={styles.control} name="preferred_language" value={fields.preferred_language} onChange={event => setFields(current => ({ ...current, preferred_language: event.target.value as "en" | "bn" }))}>
                  <option value="en">English</option>
                  <option value="bn">বাংলা</option>
                </select>
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "মুদ্রা" : "Currency"}</span>
                <input className={styles.control} name="preferred_currency" list="profile-currency-options" minLength={3} maxLength={10} pattern="[A-Za-z]+" autoCapitalize="characters" spellCheck={false} value={fields.preferred_currency} onChange={event => setFields(current => ({ ...current, preferred_currency: event.target.value }))} required />
              </label>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>{bn ? "টাইমজোন (IANA)" : "Timezone (IANA)"}</span>
                <input className={styles.control} name="timezone" list="profile-timezone-options" value={fields.timezone} maxLength={80} placeholder="Asia/Dhaka" spellCheck={false} onChange={event => setFields(current => ({ ...current, timezone: event.target.value }))} required />
              </label>
            </div>
          </section>

          <datalist id="profile-currency-options">
            <option value="BDT" /><option value="USD" /><option value="EUR" /><option value="GBP" /><option value="CNY" /><option value="INR" />
          </datalist>
          <datalist id="profile-timezone-options">
            <option value="Asia/Dhaka" /><option value="Asia/Kolkata" /><option value="Asia/Shanghai" /><option value="Asia/Singapore" /><option value="Europe/London" /><option value="America/New_York" />
          </datalist>

          <div className={`account-profile-form__wide account-form-actions ${styles.formFooter}`}>
            <p className={styles.securityNote}><AppIcon name="lock" size={15} />{bn ? "পরিবর্তনগুলো আপনার নিরাপদ account profile-এ সংরক্ষিত হবে।" : "Changes are saved to your secure customer profile and used for future orders."}</p>
            <button className="button button--primary" type="submit" disabled={saving}>
              {saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "প্রোফাইল সংরক্ষণ" : "Save profile")}
            </button>
          </div>
        </form>
      </section>

      <section className={`account-panel ${styles.addressPanel}`} aria-labelledby="address-book-heading">
        <div className={styles.addressHeader}>
          <div>
            <h2 id="address-book-heading">{bn ? "ঠিকানা বই" : "Address book"}</h2>
            <p>{bn ? "Default shipping ও billing ঠিকানা checkout এবং invoice snapshot-এ ব্যবহৃত হয়।" : "Default shipping and billing addresses are used for checkout and invoice snapshots."}</p>
          </div>
          <span className={styles.addressCount} aria-label={bn ? `${addresses.length}টি সংরক্ষিত ঠিকানা` : `${addresses.length} saved addresses`}>{addresses.length}</span>
        </div>

        {addresses.length ? (
          <div className={`account-address-grid ${styles.addressGrid}`}>
            {addresses.map(item => (
              <article key={item.id} className={`account-address-card ${styles.addressCard}`}>
                <div className={styles.addressCardTop}>
                  <span className={styles.addressIcon}><AppIcon name="package" size={17} /></span>
                  <div className={styles.addressTitle}>
                    <strong>{item.label}</strong>
                    <small>{item.recipient_name}{item.company_name ? ` · ${item.company_name}` : ""}</small>
                  </div>
                </div>
                <div className={styles.addressBadges}>
                  {item.is_default_shipping ? <span className={styles.addressBadge}>{bn ? "Default shipping" : "Default shipping"}</span> : null}
                  {item.is_default_billing ? <span className={`${styles.addressBadge} ${styles.addressBadgeBilling}`}>{bn ? "Default billing" : "Default billing"}</span> : null}
                </div>
                <address className={styles.addressBody}>
                  {item.line1}{item.line2 ? `, ${item.line2}` : ""}<br />
                  {item.city}{item.region ? `, ${item.region}` : ""} {item.postal_code || ""}<br />
                  {item.country_code}<br />
                  <span className={styles.addressPhone}>{item.phone}</span>
                </address>
                <div className={styles.addressActions}>
                  <button className="button button--ghost" type="button" onClick={() => openEdit(item)} aria-label={bn ? `${item.label} ঠিকানা সম্পাদনা করুন` : `Edit ${item.label} address`}>{bn ? "সম্পাদনা" : "Edit"}</button>
                  <button className="button button--ghost button--danger-text" type="button" onClick={() => { setError(""); setDeleteTarget(item); }} aria-label={bn ? `${item.label} ঠিকানা সরান` : `Remove ${item.label} address`}>{bn ? "সরান" : "Remove"}</button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className={styles.emptyAddress}>
            <span className={styles.emptyIcon}><AppIcon name="package" size={22} /></span>
            <h3>{bn ? "এখনো কোনো ঠিকানা নেই" : "No saved addresses yet"}</h3>
            <p>{bn ? "দ্রুত checkout ও সঠিক invoice-এর জন্য প্রথম shipping বা billing ঠিকানা যোগ করুন।" : "Add your first shipping or billing address for faster checkout and accurate invoices."}</p>
            <button className="button button--ghost" type="button" onClick={openNew}>{bn ? "প্রথম ঠিকানা যোগ করুন" : "Add first address"}</button>
          </div>
        )}
      </section>

      <AdminModal
        open={addressTarget !== null}
        onClose={closeAddressDialog}
        closeLabel={bn ? "ঠিকানা ডায়ালগ বন্ধ করুন" : "Close address dialog"}
        title={addressTarget === "new" ? (bn ? "ঠিকানা যোগ করুন" : "Add address") : (bn ? "ঠিকানা সম্পাদনা" : "Edit address")}
        description={bn ? "দেশের জন্য দুই অক্ষরের ISO code দিন, যেমন BD।" : "Use a two-letter ISO country code, such as BD."}
      >
        <form className={`admin-modal__form ${styles.addressForm}`} onSubmit={saveAddress} aria-busy={saving}>
          <label><span>{bn ? "লেবেল" : "Label"}</span><input name="label" required maxLength={80} value={address.label} onChange={event => setAddress(current => ({ ...current, label: event.target.value }))} placeholder="Office / Home" /></label>
          <label><span>{bn ? "প্রাপকের নাম" : "Recipient name"}</span><input name="recipient_name" autoComplete="name" required minLength={2} maxLength={200} value={address.recipient_name} onChange={event => setAddress(current => ({ ...current, recipient_name: event.target.value }))} /></label>
          <label className={styles.modalWide}><span>{bn ? "কোম্পানি" : "Company"}</span><input name="company_name" autoComplete="organization" maxLength={200} value={address.company_name || ""} onChange={event => setAddress(current => ({ ...current, company_name: event.target.value }))} /></label>
          <label className={styles.modalWide}><span>{bn ? "ঠিকানা ১" : "Address line 1"}</span><input name="address_line_1" autoComplete="address-line1" required minLength={3} maxLength={250} value={address.line1} onChange={event => setAddress(current => ({ ...current, line1: event.target.value }))} /></label>
          <label className={styles.modalWide}><span>{bn ? "ঠিকানা ২" : "Address line 2"}</span><input name="address_line_2" autoComplete="address-line2" maxLength={250} value={address.line2 || ""} onChange={event => setAddress(current => ({ ...current, line2: event.target.value }))} /></label>
          <label><span>{bn ? "শহর" : "City"}</span><input name="city" autoComplete="address-level2" required minLength={2} maxLength={120} value={address.city} onChange={event => setAddress(current => ({ ...current, city: event.target.value }))} /></label>
          <label><span>{bn ? "অঞ্চল" : "Region"}</span><input name="region" autoComplete="address-level1" maxLength={120} value={address.region || ""} onChange={event => setAddress(current => ({ ...current, region: event.target.value }))} /></label>
          <label><span>{bn ? "Postal code" : "Postal code"}</span><input name="postal_code" autoComplete="postal-code" maxLength={40} value={address.postal_code || ""} onChange={event => setAddress(current => ({ ...current, postal_code: event.target.value }))} /></label>
          <label><span>{bn ? "দেশের code" : "Country code"}</span><input name="country_code" autoComplete="country" required pattern="[A-Za-z]{2}" minLength={2} maxLength={2} autoCapitalize="characters" spellCheck={false} value={address.country_code} onChange={event => setAddress(current => ({ ...current, country_code: event.target.value }))} /></label>
          <label className={styles.modalWide}><span>{bn ? "ফোন" : "Phone"}</span><input name="phone" type="tel" inputMode="tel" autoComplete="tel" required minLength={5} maxLength={40} value={address.phone} onChange={event => setAddress(current => ({ ...current, phone: event.target.value }))} /></label>
          <label className="admin-checkbox-label"><input name="default_shipping" type="checkbox" checked={address.is_default_shipping} onChange={event => setAddress(current => ({ ...current, is_default_shipping: event.target.checked }))} /><span>{bn ? "Default shipping" : "Default shipping"}</span></label>
          <label className="admin-checkbox-label"><input name="default_billing" type="checkbox" checked={address.is_default_billing} onChange={event => setAddress(current => ({ ...current, is_default_billing: event.target.checked }))} /><span>{bn ? "Default billing" : "Default billing"}</span></label>
          {error ? <div className={`admin-alert admin-alert--error ${styles.modalWide}`} role="alert">{error}</div> : null}
          <div className={`admin-modal__actions ${styles.modalWide}`}>
            <button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={closeAddressDialog}>{bn ? "বাতিল" : "Cancel"}</button>
            <button className="admin-button admin-button--primary" type="submit" disabled={saving}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button>
          </div>
        </form>
      </AdminModal>

      <AdminModal
        open={deleteTarget !== null}
        onClose={closeDeleteDialog}
        closeLabel={bn ? "ঠিকানা সরানোর ডায়ালগ বন্ধ করুন" : "Close remove address dialog"}
        title={bn ? "ঠিকানাটি সরাবেন?" : "Remove address?"}
        description={bn ? "Default ঠিকানা সরালে অন্য ঠিকানা স্বয়ংক্রিয়ভাবে default হতে পারে।" : "Removing a default address may automatically promote another address."}
      >
        {error ? <div className="admin-alert admin-alert--error" role="alert">{error}</div> : null}
        <div className="admin-modal__actions">
          <button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={closeDeleteDialog}>{bn ? "বাতিল" : "Cancel"}</button>
          <button className="admin-button admin-button--danger" type="button" disabled={saving} onClick={() => void removeAddress()}>{bn ? "সরান" : "Remove"}</button>
        </div>
      </AdminModal>

      {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
    </div>
  );
}
