"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppIcon } from "../../components/app-icon";
import {
  ApiError,
  getAuthServiceStatus,
  isApiServiceUnavailable,
  registerAccount,
} from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

export default function SignupPage() {
  const [form, setForm] = useState({ username: "", email: "", phone: "", password: "" });
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [serviceState, setServiceState] = useState<"checking" | "ready" | "offline">("checking");
  const router = useRouter();
  const { locale } = useLocale();
  const bn = locale === "bn";
  const passwordChecks = {
    length: form.password.length >= 12,
    upper: /[A-Z]/.test(form.password),
    lower: /[a-z]/.test(form.password),
    number: /\d/.test(form.password),
    symbol: /[^A-Za-z0-9]/.test(form.password),
  };
  const passwordValid = Object.values(passwordChecks).every(Boolean);
  const passwordMatches = Boolean(form.password) && form.password === confirmation;

  const checkService = async () => {
    setServiceState("checking");
    const status = await getAuthServiceStatus();
    setServiceState(status.available ? "ready" : "offline");
    return status.available;
  };

  useEffect(() => {
    void checkService();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (serviceState === "offline" && !await checkService()) {
      setError(bn
        ? "Account service এখন সংযুক্ত নেই। Catalog দেখা যাবে, তবে নতুন account তৈরির জন্য backend চালু থাকতে হবে।"
        : "The account service is not connected. The catalog is available, but the backend must be online to create an account.");
      return;
    }
    if (!passwordMatches) {
      setError(bn ? "দুইটি password এক নয়।" : "The passwords do not match.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await registerAccount({
        username: form.username.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        password: form.password,
      });
      router.push("/account");
      router.refresh();
    } catch (reason) {
      if (isApiServiceUnavailable(reason)) {
        setServiceState("offline");
        setError(bn
          ? "Account service এখন সংযুক্ত নেই। আপনার তথ্য সংরক্ষণ করা হয়নি।"
          : "The account service is not connected. Your information was not saved.");
      } else if (reason instanceof ApiError && reason.status === 429) {
        setError(bn ? "অনেকবার চেষ্টা করা হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।" : "Too many attempts. Please wait before trying again.");
      } else {
        setError(reason instanceof Error ? reason.message : (bn ? "Account তৈরি করা যায়নি।" : "Account could not be created."));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="shell shell--narrow">
      <section className="auth-card">
        <div className="auth-intro"><div className="auth-intro__icon"><AppIcon name="user" size={25} /></div><p className="eyebrow">{bn ? "Customer account" : "Customer account"}</p><h1>{bn ? "SourceAI account তৈরি করুন" : "Create your SourceAI account"}</h1><p>{bn ? "তুলনা সংরক্ষণ, অর্ডার এবং delivery tracking করুন।" : "Save comparisons, place sourcing orders and follow each delivery stage."}</p><ul className="auth-benefits"><li><AppIcon name="check" size={16} />{bn ? "নিরাপদ HttpOnly session" : "Secure HttpOnly session"}</li><li><AppIcon name="check" size={16} />{bn ? "Customer ও admin role সম্পূর্ণ আলাদা" : "Customer and admin roles stay separate"}</li><li><AppIcon name="check" size={16} />{bn ? "Quote, order ও notification এক account-এ" : "Quotes, orders, and notifications in one account"}</li></ul><div className={`auth-service-status auth-service-status--${serviceState}`} role="status"><span aria-hidden /><div><strong>{serviceState === "ready" ? (bn ? "Account service online" : "Account service online") : serviceState === "checking" ? (bn ? "সংযোগ যাচাই হচ্ছে…" : "Checking connection…") : (bn ? "Account service offline" : "Account service offline")}</strong>{serviceState === "offline" ? <small>{bn ? "Backend চালু হলে registration করা যাবে।" : "Registration will be available when the backend is online."}</small> : null}</div>{serviceState === "offline" ? <button type="button" onClick={() => void checkService()}><AppIcon name="refresh" size={15} />Retry</button> : null}</div></div>
        <form onSubmit={submit}>
          <label className="auth-field"><span><AppIcon name="user" size={16} />{bn ? "Username" : "Username"}</span><div className="auth-input"><input autoCapitalize="none" autoComplete="username" minLength={3} maxLength={150} spellCheck={false} value={form.username} onChange={(event) => setForm((value) => ({ ...value, username: event.target.value }))} required /></div></label>
          <label className="auth-field"><span><AppIcon name="user" size={16} />{bn ? "Email" : "Email"}</span><div className="auth-input"><input type="email" autoComplete="email" maxLength={254} value={form.email} onChange={(event) => setForm((value) => ({ ...value, email: event.target.value }))} required /></div></label>
          <label className="auth-field"><span><AppIcon name="user" size={16} />{bn ? "Phone (ঐচ্ছিক)" : "Phone (optional)"}</span><div className="auth-input"><input autoComplete="tel" inputMode="tel" maxLength={40} value={form.phone} onChange={(event) => setForm((value) => ({ ...value, phone: event.target.value }))} /></div></label>
          <label className="auth-field"><span><AppIcon name="lock" size={16} />{bn ? "Password" : "Password"}</span><div className="auth-input"><input type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={12} maxLength={128} aria-describedby="password-policy" value={form.password} onChange={(event) => setForm((value) => ({ ...value, password: event.target.value }))} required /><button type="button" className="auth-password-toggle" aria-label={showPassword ? (bn ? "Password লুকান" : "Hide password") : (bn ? "Password দেখুন" : "Show password")} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}><AppIcon name={showPassword ? "eye-off" : "eye"} size={18} /></button></div></label>
          <ul id="password-policy" className="password-policy" aria-label={bn ? "Password-এর নিয়ম" : "Password requirements"}>
            <li className={passwordChecks.length ? "password-policy--met" : ""}>{bn ? "কমপক্ষে ১২ অক্ষর" : "At least 12 characters"}</li>
            <li className={passwordChecks.upper ? "password-policy--met" : ""}>{bn ? "একটি বড় হাতের অক্ষর" : "One uppercase letter"}</li>
            <li className={passwordChecks.lower ? "password-policy--met" : ""}>{bn ? "একটি ছোট হাতের অক্ষর" : "One lowercase letter"}</li>
            <li className={passwordChecks.number ? "password-policy--met" : ""}>{bn ? "একটি সংখ্যা" : "One number"}</li>
            <li className={passwordChecks.symbol ? "password-policy--met" : ""}>{bn ? "একটি symbol" : "One symbol"}</li>
          </ul>
          <label className="auth-field"><span><AppIcon name="lock" size={16} />{bn ? "Password নিশ্চিত করুন" : "Confirm password"}</span><div className={`auth-input${confirmation && !passwordMatches ? " auth-input--invalid" : ""}`}><input type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={12} maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} aria-invalid={Boolean(confirmation && !passwordMatches)} required /></div></label>
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          <button className="market-button auth-submit" disabled={loading || serviceState === "checking" || !passwordValid || !passwordMatches}>{loading ? (bn ? "Account তৈরি হচ্ছে…" : "Creating account…") : <><AppIcon name="shield" size={18} />{bn ? "নিরাপদ account তৈরি করুন" : "Create secure account"}</>}</button>
          <small>{bn ? "আগে থেকেই account আছে?" : "Already registered?"} <Link className="nav-link" href="/login">{bn ? "Sign in" : "Sign in"}</Link></small>
        </form>
      </section>
    </main>
  );
}
