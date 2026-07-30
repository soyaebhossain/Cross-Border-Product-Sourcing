"use client";

import { useEffect, useState } from "react";
import { useLocale } from "../../../lib/locale-context";

type Preferences = {
  compactTables: boolean;
  reducedMotion: boolean;
  desktopAlerts: boolean;
};

const defaults: Preferences = { compactTables: false, reducedMotion: false, desktopAlerts: true };
const STORAGE_KEY = "sourceai-admin-preferences";

export default function AdminSettingsPage() {
  const [preferences, setPreferences] = useState<Preferences>(defaults);
  const [saved, setSaved] = useState(false);
  const { locale, setLocale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const next = { ...defaults, ...JSON.parse(stored) as Partial<Preferences> };
        setPreferences(next);
        document.documentElement.dataset.adminDensity = next.compactTables ? "compact" : "comfortable";
        document.documentElement.dataset.reduceMotion = next.reducedMotion ? "true" : "false";
      }
    } catch {
      setPreferences(defaults);
    }
  }, []);

  const save = (event: React.FormEvent) => {
    event.preventDefault();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
    document.documentElement.dataset.adminDensity = preferences.compactTables ? "compact" : "comfortable";
    document.documentElement.dataset.reduceMotion = preferences.reducedMotion ? "true" : "false";
    setSaved(true);
    window.setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="admin-page">
      <header className="admin-page-header"><div><p className="admin-eyebrow">{bn ? "ওয়ার্কস্পেস কনফিগারেশন" : "Workspace configuration"}</p><h1>{bn ? "সেটিংস" : "Settings"}</h1><p>{bn ? "Language, display ও operational defaults পরিচালনা করুন।" : "Manage language, display and operational defaults."}</p></div></header>
      <form className="admin-settings-grid" onSubmit={save}>
        <section className="admin-card">
          <div className="admin-card__header"><div><h2>{bn ? "ভাষা ও অঞ্চল" : "Language and region"}</h2><p>{bn ? "তারিখ Asia/Dhaka timezone-এ দেখানো হয়।" : "Dates are displayed in the Asia/Dhaka timezone."}</p></div></div>
          <div className="admin-setting-row"><div><strong>{bn ? "ইন্টারফেস ভাষা" : "Interface language"}</strong><span>{bn ? "এই browser-এ সংরক্ষিত" : "Saved on this browser"}</span></div><select aria-label={bn ? "ইন্টারফেস ভাষা" : "Interface language"} value={locale} onChange={event => setLocale(event.target.value === "bn" ? "bn" : "en")}><option value="en">English</option><option value="bn">বাংলা</option></select></div>
          <div className="admin-setting-row"><div><strong>{bn ? "অপারেশন timezone" : "Operations timezone"}</strong><span>{bn ? "অর্ডার ও audit timestamp" : "Order and audit timestamps"}</span></div><output>Asia/Dhaka (UTC+06:00)</output></div>
          <div className="admin-setting-row"><div><strong>{bn ? "হিসাবের মুদ্রা" : "Accounting currency"}</strong><span>{bn ? "ল্যান্ডেড কস্ট ও payment" : "Landed cost and payments"}</span></div><output>BDT</output></div>
        </section>

        <section className="admin-card">
          <div className="admin-card__header"><div><h2>{bn ? "ডিসপ্লে ও অ্যাক্সেসিবিলিটি" : "Display and accessibility"}</h2><p>{bn ? "আপনার admin workspace-এর জন্য।" : "Personal to your admin workspace."}</p></div></div>
          <label className="admin-switch-row"><span><strong>{bn ? "Compact table" : "Compact tables"}</strong><small>{bn ? "এক স্ক্রিনে আরও row দেখুন" : "Show more rows on each screen"}</small></span><input type="checkbox" checked={preferences.compactTables} onChange={event => setPreferences(current => ({ ...current, compactTables: event.target.checked }))} /></label>
          <label className="admin-switch-row"><span><strong>{bn ? "Motion কমান" : "Reduce motion"}</strong><small>{bn ? "Animation ও transition সীমিত করুন" : "Limit animations and transitions"}</small></span><input type="checkbox" checked={preferences.reducedMotion} onChange={event => setPreferences(current => ({ ...current, reducedMotion: event.target.checked }))} /></label>
          <label className="admin-switch-row"><span><strong>{bn ? "Operational alert" : "Operational alerts"}</strong><small>{bn ? "Queue reminder দেখান" : "Show queue reminders in the dashboard"}</small></span><input type="checkbox" checked={preferences.desktopAlerts} onChange={event => setPreferences(current => ({ ...current, desktopAlerts: event.target.checked }))} /></label>
        </section>

        <section className="admin-card admin-settings-wide">
          <div className="admin-card__header"><div><h2>{bn ? "নিরাপত্তা সীমা" : "Security boundaries"}</h2><p>{bn ? "Production access policy-এর বর্তমান UI contract।" : "Current UI contract for production access policy."}</p></div></div>
          <div className="admin-security-list">
            <div><span className="admin-security-icon" aria-hidden>✓</span><div><strong>{bn ? "Role-based route protection" : "Role-based route protection"}</strong><small>{bn ? "Customer-কে admin ও research থেকে redirect করা হয়; API-ও role যাচাই করে।" : "Customers are redirected away from admin and research; APIs also enforce role checks."}</small></div></div>
            <div><span className="admin-security-icon" aria-hidden>✓</span><div><strong>{bn ? "HttpOnly session" : "HttpOnly session"}</strong><small>{bn ? "Browser script-এ credential রাখা হয় না।" : "Credentials are not exposed to browser scripts."}</small></div></div>
            <div><span className="admin-security-icon admin-security-icon--pending" aria-hidden>!</span><div><strong>{bn ? "Production identity policy" : "Production identity policy"}</strong><small>{bn ? "Launch-এর আগে MFA, rate limit ও secure admin provisioning environment-এ enforce করুন।" : "Enforce MFA, rate limiting and secure admin provisioning in the production environment before launch."}</small></div></div>
          </div>
        </section>
        <div className="admin-settings-actions"><button className="admin-button admin-button--primary" type="submit">{bn ? "পছন্দ সংরক্ষণ" : "Save preferences"}</button>{saved ? <span role="status">{bn ? "সংরক্ষিত হয়েছে" : "Preferences saved"}</span> : null}</div>
      </form>
    </div>
  );
}
