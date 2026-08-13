"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppIcon } from "../../components/app-icon";
import { ApiError, confirmPasswordReset, isApiServiceUnavailable } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

const PASSWORD_MIN_LENGTH = 8;

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [tokenReady, setTokenReady] = useState(false);
  const [invalidLink, setInvalidLink] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");
  const statusHeading = useRef<HTMLHeadingElement>(null);
  const { locale } = useLocale();
  const bn = locale === "bn";
  const passwordChecks = {
    length: password.length >= PASSWORD_MIN_LENGTH,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /\d/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
  };
  const passwordValid = Object.values(passwordChecks).every(Boolean);
  const passwordMatches = Boolean(password) && password === confirmation;

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const value = fragment.get("token") || "";
    window.history.replaceState(null, "", window.location.pathname);
    setToken(value);
    setInvalidLink(!value);
    setTokenReady(true);
  }, []);

  useEffect(() => {
    if (complete || invalidLink) statusHeading.current?.focus();
  }, [complete, invalidLink]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!passwordMatches || !passwordValid || !token) return;
    setLoading(true);
    setError("");
    try {
      await confirmPasswordReset(token, password);
      setPassword("");
      setConfirmation("");
      setToken("");
      setComplete(true);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 400 && /invalid|expired|already used/i.test(reason.message)) {
        setToken("");
        setInvalidLink(true);
      } else if (isApiServiceUnavailable(reason)) {
        setError(bn ? "Account service এখন সংযুক্ত নেই। আবার চেষ্টা করুন।" : "The account service is not connected. Please try again.");
      } else if (reason instanceof ApiError && /username|email fragments/i.test(reason.message)) {
        setError(bn ? "Password-এ আপনার username বা email-এর নামের অংশ ব্যবহার করবেন না।" : "Do not include your username or the name part of your email in the password.");
      } else if (reason instanceof ApiError) {
        setError(reason.message);
      } else {
        setError(bn ? "Password আপডেট করা যায়নি। আবার চেষ্টা করুন।" : "The password could not be updated. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const unavailable = tokenReady && invalidLink;
  return (
    <main className="shell shell--narrow">
      <section className="auth-card">
        <div className="auth-intro">
          <div className="auth-intro__icon"><AppIcon name="shield" size={25} /></div>
          <p className="eyebrow">{bn ? "নিরাপদ credential" : "Secure credentials"}</p>
          <h1>{bn ? "নতুন password দিন" : "Choose a new password"}</h1>
          <p>{bn ? "নতুন password শক্তিশালী ও account identifier থেকে আলাদা রাখুন।" : "Use a strong password that is different from your account identifiers."}</p>
          <ul className="auth-benefits">
            <li><AppIcon name="check" size={16} />{bn ? "Reset link একবার ব্যবহারযোগ্য" : "The reset link is single-use"}</li>
            <li><AppIcon name="check" size={16} />{bn ? "সব পুরোনো session বাতিল হবে" : "All existing sessions will be revoked"}</li>
            <li><AppIcon name="check" size={16} />{bn ? "Admin MFA অক্ষত থাকবে" : "Admin MFA remains protected"}</li>
          </ul>
        </div>
        {!tokenReady ? <form><div className="empty-state" role="status">{bn ? "Reset link যাচাই হচ্ছে…" : "Checking reset link…"}</div></form> : complete ? <form className="auth-recovery-state" aria-live="polite">
          <div className="auth-recovery-state__icon"><AppIcon name="check" size={26} /></div>
          <p className="eyebrow">{bn ? "সম্পন্ন" : "Complete"}</p>
          <h2 ref={statusHeading} tabIndex={-1}>{bn ? "Password আপডেট হয়েছে" : "Password updated"}</h2>
          <p>{bn ? "আগের সব session sign out করা হয়েছে। নতুন password দিয়ে আবার sign in করুন।" : "All existing sessions have been signed out. Sign in again with your new password."}</p>
          <Link className="market-button auth-submit" href="/login"><AppIcon name="lock" size={18} />{bn ? "নতুন password দিয়ে sign in" : "Sign in with new password"}</Link>
        </form> : unavailable ? <form className="auth-recovery-state" aria-live="polite">
          <div className="auth-recovery-state__icon"><AppIcon name="alert" size={26} /></div>
          <p className="eyebrow">{bn ? "Link পাওয়া যায়নি" : "Link unavailable"}</p>
          <h2 ref={statusHeading} tabIndex={-1}>{bn ? "Reset link ব্যবহার করা যাবে না" : "Reset link unavailable"}</h2>
          <p>{bn ? "এই reset link invalid, expire হয়েছে অথবা আগেই ব্যবহার করা হয়েছে।" : "This reset link is invalid, expired, or already used."}</p>
          <Link className="market-button auth-submit" href="/forgot-password"><AppIcon name="refresh" size={18} />{bn ? "নতুন link চান" : "Request a new link"}</Link>
          <small><Link className="nav-link" href="/login">← {bn ? "Sign in-এ ফিরুন" : "Back to sign in"}</Link></small>
        </form> : <form name="password-reset-confirm" autoComplete="on" onSubmit={submit}>
          <label className="auth-field" htmlFor="new-password"><span><AppIcon name="lock" size={16} />{bn ? "নতুন password" : "New password"}</span><div className="auth-input"><input id="new-password" name="new-password" type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} maxLength={128} aria-describedby="reset-password-policy" value={password} onChange={event => setPassword(event.target.value)} required /><button type="button" className="auth-password-toggle" aria-label={showPassword ? (bn ? "Password লুকান" : "Hide password") : (bn ? "Password দেখুন" : "Show password")} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}><AppIcon name={showPassword ? "eye-off" : "eye"} size={18} /></button></div></label>
          <ul id="reset-password-policy" className="password-policy" aria-label={bn ? "Password-এর নিয়ম" : "Password requirements"}>
            <li className={passwordChecks.length ? "password-policy--met" : ""}>{bn ? "কমপক্ষে ৮ অক্ষর" : "At least 8 characters"}</li>
            <li className={passwordChecks.upper ? "password-policy--met" : ""}>{bn ? "একটি বড় হাতের অক্ষর" : "One uppercase letter"}</li>
            <li className={passwordChecks.lower ? "password-policy--met" : ""}>{bn ? "একটি ছোট হাতের অক্ষর" : "One lowercase letter"}</li>
            <li className={passwordChecks.number ? "password-policy--met" : ""}>{bn ? "একটি সংখ্যা" : "One number"}</li>
            <li className={passwordChecks.symbol ? "password-policy--met" : ""}>{bn ? "একটি symbol" : "One symbol"}</li>
          </ul>
          <small>{bn ? "Username বা email-এর নামের অংশ password-এ ব্যবহার করবেন না।" : "Do not include your username or the name part of your email."}</small>
          <label className="auth-field" htmlFor="confirm-new-password"><span><AppIcon name="lock" size={16} />{bn ? "নতুন password নিশ্চিত করুন" : "Confirm new password"}</span><div className={`auth-input${confirmation && !passwordMatches ? " auth-input--invalid" : ""}`}><input id="confirm-new-password" name="confirm-password" type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} aria-invalid={Boolean(confirmation && !passwordMatches)} aria-describedby={confirmation && !passwordMatches ? "password-mismatch" : undefined} required /></div></label>
          {confirmation && !passwordMatches ? <small id="password-mismatch" className="form-error" role="alert">{bn ? "দুইটি password এক নয়।" : "The passwords do not match."}</small> : null}
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          <button className="market-button auth-submit" type="submit" disabled={loading || !passwordValid || !passwordMatches}>{loading ? (bn ? "Password আপডেট হচ্ছে…" : "Updating password…") : <><AppIcon name="shield" size={18} />{bn ? "Password নিরাপদে আপডেট করুন" : "Update password securely"}</>}</button>
          <small><Link className="nav-link" href="/login">← {bn ? "Sign in-এ ফিরুন" : "Back to sign in"}</Link></small>
        </form>}
      </section>
    </main>
  );
}
