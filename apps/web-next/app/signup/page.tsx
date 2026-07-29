"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { registerAccount } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

export default function SignupPage() {
  const [form, setForm] = useState({ username: "", email: "", phone: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
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

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
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
      setError(reason instanceof Error ? reason.message : (bn ? "Account তৈরি করা যায়নি।" : "Account could not be created."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="shell shell--narrow">
      <section className="auth-card">
        <div><p className="eyebrow">{bn ? "Customer account" : "Customer account"}</p><h1>{bn ? "SourceAI account তৈরি করুন" : "Create your SourceAI account"}</h1><p>{bn ? "তুলনা সংরক্ষণ, অর্ডার এবং delivery tracking করুন।" : "Save comparisons, place sourcing orders and follow each delivery stage."}</p></div>
        <form onSubmit={submit}>
          <label>{bn ? "Username" : "Username"}<input autoComplete="username" maxLength={150} value={form.username} onChange={(event) => setForm((value) => ({ ...value, username: event.target.value }))} required /></label>
          <label>{bn ? "Email (ঐচ্ছিক)" : "Email (optional)"}<input type="email" autoComplete="email" maxLength={254} value={form.email} onChange={(event) => setForm((value) => ({ ...value, email: event.target.value }))} /></label>
          <label>{bn ? "Phone (ঐচ্ছিক)" : "Phone (optional)"}<input autoComplete="tel" maxLength={40} value={form.phone} onChange={(event) => setForm((value) => ({ ...value, phone: event.target.value }))} /></label>
          <label>{bn ? "Password" : "Password"}<input type="password" autoComplete="new-password" minLength={12} maxLength={128} aria-describedby="password-policy" value={form.password} onChange={(event) => setForm((value) => ({ ...value, password: event.target.value }))} required /></label>
          <ul id="password-policy" className="password-policy" aria-label={bn ? "Password-এর নিয়ম" : "Password requirements"}>
            <li className={passwordChecks.length ? "password-policy--met" : ""}>{bn ? "কমপক্ষে ১২ অক্ষর" : "At least 12 characters"}</li>
            <li className={passwordChecks.upper ? "password-policy--met" : ""}>{bn ? "একটি বড় হাতের অক্ষর" : "One uppercase letter"}</li>
            <li className={passwordChecks.lower ? "password-policy--met" : ""}>{bn ? "একটি ছোট হাতের অক্ষর" : "One lowercase letter"}</li>
            <li className={passwordChecks.number ? "password-policy--met" : ""}>{bn ? "একটি সংখ্যা" : "One number"}</li>
            <li className={passwordChecks.symbol ? "password-policy--met" : ""}>{bn ? "একটি symbol" : "One symbol"}</li>
          </ul>
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          <button className="market-button" disabled={loading || !passwordValid}>{loading ? (bn ? "Account তৈরি হচ্ছে…" : "Creating account…") : (bn ? "Account তৈরি করুন" : "Create account")}</button>
          <small>{bn ? "আগে থেকেই account আছে?" : "Already registered?"} <Link className="nav-link" href="/login">{bn ? "Sign in" : "Sign in"}</Link></small>
        </form>
      </section>
    </main>
  );
}
