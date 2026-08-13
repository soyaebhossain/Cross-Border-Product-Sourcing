"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppIcon } from "../../components/app-icon";
import {
  ApiError,
  getAuthServiceStatus,
  isApiServiceUnavailable,
  requestPasswordReset,
} from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

type ServiceState = "checking" | "ready" | "offline" | "email-unavailable";

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [errorReference, setErrorReference] = useState("");
  const successHeading = useRef<HTMLHeadingElement>(null);
  const { locale } = useLocale();
  const bn = locale === "bn";

  const checkService = async () => {
    setServiceState("checking");
    const status = await getAuthServiceStatus();
    const nextState: ServiceState = !status.available
      ? "offline"
      : status.passwordResetEmailConfigured
        ? "ready"
        : "email-unavailable";
    setServiceState(nextState);
    return nextState;
  };

  useEffect(() => {
    void checkService();
  }, []);

  useEffect(() => {
    if (sent) successHeading.current?.focus();
  }, [sent]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (serviceState !== "ready" && await checkService() !== "ready") {
      return;
    }
    setLoading(true);
    setError("");
    setErrorReference("");
    try {
      await requestPasswordReset(identifier.trim());
      setSent(true);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 503 && /reset email/i.test(reason.message)) {
        setServiceState("email-unavailable");
        setError(bn ? "Password reset email সাময়িকভাবে পাওয়া যাচ্ছে না। Support-এর সাথে যোগাযোগ করুন।" : "Password reset email is temporarily unavailable. Please contact support.");
      } else if (isApiServiceUnavailable(reason)) {
        setServiceState("offline");
        setError(bn ? "Account service এখন সংযুক্ত নেই।" : "The account service is not connected.");
      } else if (reason instanceof ApiError && reason.status === 429) {
        setError(bn ? "অনেকবার চেষ্টা করা হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।" : "Too many attempts. Please wait before trying again.");
      } else {
        setError(bn ? "Reset request পাঠানো যায়নি। আবার চেষ্টা করুন।" : "The reset request could not be sent. Please try again.");
      }
      if (reason instanceof ApiError) setErrorReference(reason.requestId || "");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="shell shell--narrow">
      <section className="auth-card">
        <div className="auth-intro">
          <div className="auth-intro__icon"><AppIcon name="lock" size={25} /></div>
          <p className="eyebrow">{bn ? "Account পুনরুদ্ধার" : "Account recovery"}</p>
          <h1>{bn ? "Password রিসেট করুন" : "Reset your password"}</h1>
          <p>{bn
            ? "আপনার username, email অথবা phone দিন। যোগ্য account-এ নিবন্ধিত email থাকলে আমরা একটি নিরাপদ reset link পাঠাব।"
            : "Enter your username, email, or phone. If an eligible account has a registered email, we’ll send a secure reset link."}</p>
          <ul className="auth-benefits">
            <li><AppIcon name="check" size={16} />{bn ? "Link ৩০ মিনিটে expire হবে" : "The link expires in 30 minutes"}</li>
            <li><AppIcon name="check" size={16} />{bn ? "Link একবারই ব্যবহার করা যাবে" : "The link can be used only once"}</li>
            <li><AppIcon name="check" size={16} />{bn ? "পুরোনো session sign out হবে" : "Existing sessions will be signed out"}</li>
          </ul>
          <div className={`auth-service-status auth-service-status--${serviceState}`} role="status">
            <span aria-hidden />
            <div>
              <strong>{serviceState === "ready"
                ? (bn ? "Reset email service configured" : "Reset email service configured")
                : serviceState === "checking"
                  ? (bn ? "সংযোগ যাচাই হচ্ছে…" : "Checking connection…")
                  : serviceState === "email-unavailable"
                    ? (bn ? "Reset email setup প্রয়োজন" : "Reset email setup required")
                    : (bn ? "Account service offline" : "Account service offline")}</strong>
              {serviceState === "email-unavailable" ? <small>{bn
                ? "নিরাপদ email provider configure না হওয়া পর্যন্ত reset link পাঠানো যাবে না।"
                : "Reset links cannot be sent until the secure email provider is configured."}</small> : null}
            </div>
            {serviceState === "offline" ? <button type="button" onClick={() => void checkService()}><AppIcon name="refresh" size={15} />Retry</button> : null}
          </div>
        </div>
        {sent ? <form className="auth-recovery-state" aria-live="polite">
          <div className="auth-recovery-state__icon"><AppIcon name="check" size={26} /></div>
          <p className="eyebrow">{bn ? "নিরাপদ response" : "Secure response"}</p>
          <h2 ref={successHeading} tabIndex={-1}>{bn ? "আপনার email দেখুন" : "Check your email"}</h2>
          <p>{bn
            ? "যোগ্য account মিললে reset link পাঠানো হয়েছে। Spam folder-ও দেখুন।"
            : "If an eligible account matches, a reset link has been sent. Check your spam folder too."}</p>
          <Link className="market-button auth-submit" href="/login"><AppIcon name="arrow-left" size={17} />{bn ? "Sign in-এ ফিরুন" : "Back to sign in"}</Link>
          <button className="auth-text-button" type="button" onClick={() => { setSent(false); setError(""); }}>{bn ? "অন্য account চেষ্টা করুন" : "Try another account"}</button>
        </form> : <form name="password-reset-request" autoComplete="on" onSubmit={submit}>
          <label className="auth-field" htmlFor="reset-identifier">
            <span><AppIcon name="user" size={16} />{bn ? "Username, email অথবা phone" : "Username, email or phone"}</span>
            <div className="auth-input"><input id="reset-identifier" name="identifier" type="text" autoCapitalize="none" autoComplete="username" spellCheck={false} maxLength={320} value={identifier} onChange={event => setIdentifier(event.target.value)} required /></div>
          </label>
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          {errorReference ? <small className="auth-error-reference">Support reference: <code>{errorReference}</code></small> : null}
          <button className="market-button auth-submit" type="submit" disabled={loading || serviceState !== "ready"}>{loading
            ? (bn ? "Link পাঠানো হচ্ছে…" : "Sending link…")
            : serviceState === "email-unavailable"
              ? <><AppIcon name="lock" size={18} />{bn ? "Email setup প্রয়োজন" : "Email setup required"}</>
              : <><AppIcon name="lock" size={18} />{bn ? "Reset link পাঠান" : "Send reset link"}</>}</button>
          <small><Link className="nav-link" href="/login">← {bn ? "Sign in-এ ফিরুন" : "Back to sign in"}</Link></small>
        </form>}
      </section>
    </main>
  );
}
