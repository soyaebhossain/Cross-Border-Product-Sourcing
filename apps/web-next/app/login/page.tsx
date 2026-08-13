"use client";

import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppIcon, GoogleIcon } from "../../components/app-icon";
import {
  ApiError,
  confirmMfaEnrollment,
  getAuthServiceStatus,
  isApiServiceUnavailable,
  loginWithCredentials,
  startGoogleLogin,
  startMfaEnrollment,
  verifyMfaLogin,
  type CurrentUser,
  type MfaRequired,
} from "../../lib/api";
import { useLocale } from "../../lib/locale-context";
import {
  getRememberedIdentifier,
  updateRememberedIdentifier,
  type LoginPortal,
} from "../../lib/remembered-login";

type Portal = LoginPortal;
type Enrollment = { secret: string; otpauth_uri: string };
type ServiceState = "checking" | "ready" | "offline";

export default function LoginPage() {
  const [portal, setPortal] = useState<Portal>("customer");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState(false);
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [errorReference, setErrorReference] = useState("");
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [mfa, setMfa] = useState<MfaRequired | null>(null);
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [codesStored, setCodesStored] = useState(false);
  const [authenticatedUser, setAuthenticatedUser] = useState<CurrentUser | null>(null);
  const [copyStatus, setCopyStatus] = useState("");
  const router = useRouter();
  const { locale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialPortal: Portal = params.get("portal") === "admin" ? "admin" : "customer";
    setPortal(initialPortal);
    const rememberedIdentifier = getRememberedIdentifier(initialPortal);
    if (rememberedIdentifier) setIdentifier(rememberedIdentifier);
    if (params.get("social_error")) setError("Google sign-in was not completed. Please try again or use email and password.");
    void checkService();
  }, []);

  const checkService = async () => {
    setServiceState("checking");
    const result = await getAuthServiceStatus();
    setServiceState(result.available ? "ready" : "offline");
    return result.available;
  };

  const redirectAfterAuth = (role: string) => {
    const next = new URLSearchParams(window.location.search).get("next");
    const privileged = role === "admin" || role === "operator";
    const localNext = next?.startsWith("/") && !next.startsWith("//") ? next : null;
    const privilegedPath = Boolean(localNext && /^\/(?:admin|research)(?:\/|$|\?)/.test(localNext));
    const safeNext = localNext && (privileged || !privilegedPath) ? localNext : null;
    router.push((safeNext || (privileged ? "/admin" : "/account")) as Route);
    router.refresh();
  };

  const selectPortal = (nextPortal: Portal) => {
    setPortal(nextPortal);
    setIdentifier(getRememberedIdentifier(nextPortal));
    setPassword("");
    setShowPassword(false);
    setError("");
    setErrorReference("");
    const params = new URLSearchParams(window.location.search);
    if (nextPortal === "admin") params.set("portal", "admin");
    else params.delete("portal");
    const query = params.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
  };

  const loginErrorMessage = (reason: unknown) => {
    setErrorReference(reason instanceof ApiError ? reason.requestId || "" : "");
    if (isApiServiceUnavailable(reason)) {
      setServiceState("offline");
      return bn
        ? "Account service এখন সংযুক্ত নেই। আপনার credential ভুল নয়—service চালু হলে আবার চেষ্টা করুন।"
        : "The account service is not connected right now. Your credentials were not rejected—please retry when the service is online.";
    }
    if (reason instanceof ApiError) {
      if (reason.status === 401) {
        return bn
          ? "ইউজারনেম/email/phone অথবা password সঠিক নয়।"
          : "The username, email, phone, or password is incorrect.";
      }
      if (reason.status === 403) {
        return portal === "admin"
          ? (bn ? "এই account-এ admin/operator access নেই। Customer sign in ব্যবহার করুন।" : "This account does not have admin/operator access. Use customer sign in.")
          : (bn ? "এটি admin/operator account। Admin access নির্বাচন করুন।" : "This is an admin/operator account. Choose admin access.");
      }
      if (reason.status === 423) {
        const wait = reason.retryAfter ? Math.max(1, Math.ceil(reason.retryAfter / 60)) : null;
        return wait
          ? (bn ? `নিরাপত্তার জন্য account সাময়িকভাবে locked। প্রায় ${wait} মিনিট পর চেষ্টা করুন।` : `The account is temporarily locked for security. Try again in about ${wait} minute${wait === 1 ? "" : "s"}.`)
          : (bn ? "নিরাপত্তার জন্য account সাময়িকভাবে locked। কিছুক্ষণ পর চেষ্টা করুন।" : "The account is temporarily locked for security. Please try again later.");
      }
      if (reason.status === 429) {
        return bn
          ? "অনেকবার চেষ্টা করা হয়েছে। কিছুক্ষণ অপেক্ষা করে আবার চেষ্টা করুন।"
          : "Too many attempts. Wait a moment before trying again.";
      }
    }
    return bn ? "Sign in সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।" : "Sign in could not be completed. Please try again.";
  };

  const resetChallenge = () => {
    setMfa(null);
    setEnrollment(null);
    setMfaCode("");
    setRecoveryMode(false);
    setRecoveryCodes([]);
    setCodesStored(false);
    setAuthenticatedUser(null);
    setPassword("");
    setError("");
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (serviceState === "offline" && !await checkService()) {
      setError(loginErrorMessage(new ApiError("Account service unavailable", { code: "service_unavailable" })));
      return;
    }
    setLoading(true);
    setError("");
    setErrorReference("");
    try {
      const result = await loginWithCredentials(identifier, password, remember, portal);
      updateRememberedIdentifier(portal, identifier, remember);
      if ("mfa_required" in result) {
        setMfa(result);
        setPassword("");
        if (result.mfa_enrollment_required) {
          setEnrollment(await startMfaEnrollment(result.mfa_token));
        }
        return;
      }
      redirectAfterAuth(result.user.role);
    } catch (reason) {
      setError(loginErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  };

  const submitMfa = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!mfa) return;
    setLoading(true);
    setError("");
    try {
      if (mfa.mfa_enrollment_required) {
        const result = await confirmMfaEnrollment(mfa.mfa_token, mfaCode.replace(/\s/g, ""));
        setRecoveryCodes(result.recovery_codes);
        setAuthenticatedUser(result.user);
        setMfaCode("");
      } else {
        const value = mfaCode.trim();
        const result = await verifyMfaLogin(mfa.mfa_token, recoveryMode ? { recovery_code: value } : { code: value.replace(/\s/g, "") });
        redirectAfterAuth(result.user.role);
      }
    } catch {
      setError(recoveryMode
        ? (bn ? "Recovery code সঠিক নয়, ব্যবহৃত হয়েছে, অথবা challenge-এর মেয়াদ শেষ।" : "The recovery code is invalid, already used, or the challenge expired.")
        : (bn ? "Authenticator code সঠিক নয় অথবা challenge-এর মেয়াদ শেষ।" : "The authenticator code is invalid or the challenge expired."));
    } finally {
      setLoading(false);
    }
  };

  const copyRecoveryCodes = async () => {
    try {
      await navigator.clipboard.writeText(recoveryCodes.join("\n"));
      setCopyStatus(bn ? "কপি হয়েছে" : "Copied");
    } catch {
      setCopyStatus(bn ? "কপি করা যায়নি—ম্যানুয়ালি সংরক্ষণ করুন" : "Could not copy—save them manually");
    }
  };

  const downloadRecoveryCodes = () => {
    const blob = new Blob([recoveryCodes.join("\r\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sourceai-mfa-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  if (recoveryCodes.length && authenticatedUser) {
    return <main className="shell shell--narrow">
      <section className="auth-card auth-card--single" aria-labelledby="recovery-title">
        <div>
          <p className="eyebrow">{bn ? "একবারই দেখানো হবে" : "Shown once"}</p>
          <h1 id="recovery-title">{bn ? "Recovery code নিরাপদে রাখুন" : "Store your recovery codes safely"}</h1>
          <p>{bn ? "Authenticator হারালে প্রতিটি code একবার ব্যবহার করা যাবে। পেজ ছাড়লে এগুলো আর দেখানো হবে না।" : "Each code can be used once if your authenticator is unavailable. They will not be shown again after you leave this page."}</p>
          <div className="mfa-recovery-codes" role="list" aria-label={bn ? "Recovery code" : "Recovery codes"}>{recoveryCodes.map(code => <code role="listitem" key={code}>{code}</code>)}</div>
          <div className="form-actions"><button className="button button--ghost" type="button" onClick={copyRecoveryCodes}>{bn ? "সব কপি করুন" : "Copy all"}</button><button className="button button--ghost" type="button" onClick={downloadRecoveryCodes}>{bn ? "Text file ডাউনলোড" : "Download text file"}</button>{copyStatus ? <span role="status">{copyStatus}</span> : null}</div>
          <label className="remember-login"><input type="checkbox" checked={codesStored} onChange={event => setCodesStored(event.target.checked)} /><span>{bn ? "আমি codeগুলো password manager বা নিরাপদ স্থানে রেখেছি" : "I stored these codes in a password manager or another safe place"}</span></label>
          <button className="market-button" type="button" disabled={!codesStored} onClick={() => redirectAfterAuth(authenticatedUser.role)}>{bn ? "Admin dashboard খুলুন" : "Continue to admin dashboard"}</button>
        </div>
      </section>
    </main>;
  }

  if (mfa) {
    const enrollmentRequired = mfa.mfa_enrollment_required;
    return <main className="shell shell--narrow">
      <section className="auth-card auth-card--single">
        <div>
          <p className="eyebrow">{enrollmentRequired ? (bn ? "প্রথমবারের নিরাপত্তা সেটআপ" : "First-time security setup") : (bn ? "দ্বিতীয় নিরাপত্তা ধাপ" : "Second security step")}</p>
          <h1>{enrollmentRequired ? (bn ? "Authenticator app সংযুক্ত করুন" : "Connect an authenticator app") : (bn ? "নিরাপত্তা code দিন" : "Enter your security code")}</h1>
          <p>{bn ? `এই challenge প্রায় ${Math.max(1, Math.floor(mfa.expires_in / 60))} মিনিটের মধ্যে শেষ হবে।` : `This challenge expires in about ${Math.max(1, Math.floor(mfa.expires_in / 60))} minutes.`}</p>
        </div>
        {enrollmentRequired && enrollment ? <div className="mfa-enrollment">
          <ol>
            <li>{bn ? "Google Authenticator, Microsoft Authenticator বা compatible TOTP app খুলুন।" : "Open Google Authenticator, Microsoft Authenticator or another compatible TOTP app."}</li>
            <li>{bn ? "নিচের secret key ম্যানুয়ালি যোগ করুন অথবা authenticator link খুলুন।" : "Add the secret key manually or open the authenticator link."}</li>
            <li>{bn ? "App-এর ৬ সংখ্যার code দিয়ে setup নিশ্চিত করুন।" : "Confirm setup with the current six-digit code from the app."}</li>
          </ol>
          <label><span>{bn ? "Secret key" : "Secret key"}</span><output className="mfa-secret">{enrollment.secret}</output></label>
          <a className="button button--ghost" href={enrollment.otpauth_uri}>{bn ? "Authenticator app-এ খুলুন" : "Open in authenticator app"}</a>
        </div> : null}
        <form onSubmit={submitMfa}>
          {!enrollmentRequired ? <div className="login-role-switch" role="group" aria-label={bn ? "Verification পদ্ধতি" : "Verification method"}><button type="button" className={!recoveryMode ? "login-role-switch__active" : ""} aria-pressed={!recoveryMode} onClick={() => { setRecoveryMode(false); setMfaCode(""); setError(""); }}>{bn ? "Authenticator code" : "Authenticator code"}</button><button type="button" className={recoveryMode ? "login-role-switch__active" : ""} aria-pressed={recoveryMode} onClick={() => { setRecoveryMode(true); setMfaCode(""); setError(""); }}>{bn ? "Recovery code" : "Recovery code"}</button></div> : null}
          <label>{recoveryMode ? (bn ? "একবার ব্যবহারযোগ্য recovery code" : "One-time recovery code") : (bn ? "৬ সংখ্যার authenticator code" : "Six-digit authenticator code")}<input autoFocus autoComplete="one-time-code" inputMode={recoveryMode ? "text" : "numeric"} pattern={recoveryMode ? undefined : "[0-9]{6}"} minLength={6} maxLength={recoveryMode ? 30 : 6} value={mfaCode} onChange={event => setMfaCode(event.target.value)} required /></label>
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          <button className="market-button" disabled={loading || mfaCode.trim().length < 6}>{loading ? (bn ? "যাচাই হচ্ছে…" : "Verifying…") : enrollmentRequired ? (bn ? "MFA চালু ও নিশ্চিত করুন" : "Enable and confirm MFA") : (bn ? "যাচাই করে প্রবেশ করুন" : "Verify and sign in")}</button>
          <button className="auth-text-button" type="button" onClick={resetChallenge} disabled={loading}>{bn ? "Login-এ ফিরে যান" : "Back to sign in"}</button>
        </form>
      </section>
    </main>;
  }

  return (
    <main className="shell shell--narrow auth-page">
      <section className="auth-card auth-card--login" aria-labelledby="login-title">
        <aside className={`auth-login-brand auth-login-brand--${portal}`}>
          <div>
            <Link className="auth-brand-lockup" href="/" aria-label={bn ? "SourceAI হোম" : "SourceAI home"}>
              <span aria-hidden>S</span>
              <div><strong>Source<span>AI</span></strong><small>{bn ? "Sourcing decision platform" : "Sourcing decision platform"}</small></div>
            </Link>
            <div className="auth-login-brand__content">
              <p className="eyebrow">{portal === "admin" ? (bn ? "নিয়ন্ত্রিত operations access" : "Controlled operations access") : (bn ? "নিরাপদ sourcing workspace" : "Secure sourcing workspace")}</p>
              <h2>{portal === "admin" ? (bn ? "নিয়ন্ত্রণ, স্বচ্ছতা ও জবাবদিহির সঙ্গে পরিচালনা করুন।" : "Operate with control, clarity, and accountability.") : (bn ? "আত্মবিশ্বাসের সঙ্গে global sourcing পরিচালনা করুন।" : "Source globally with confidence and control.")}</h2>
              <p>{portal === "admin" ? (bn ? "অনুমোদিত operations team-এর জন্য সুরক্ষিত control center access।" : "Secure control-center access for authorized operations teams.") : (bn ? "একটি account থেকে quote, order, payment ও delivery progress পরিচালনা করুন।" : "Manage quotes, orders, payments, and delivery progress from one account.")}</p>
              <ul className="auth-benefits">
                {portal === "admin" ? <>
                  <li><AppIcon name="check" size={16} />{bn ? "MFA-সুরক্ষিত privileged access" : "MFA-protected privileged access"}</li>
                  <li><AppIcon name="check" size={16} />{bn ? "Role-based permissions" : "Role-based permissions"}</li>
                  <li><AppIcon name="check" size={16} />{bn ? "Auditable operational actions" : "Auditable operational actions"}</li>
                </> : <>
                  <li><AppIcon name="check" size={16} />{bn ? "Saved quote ও comparison" : "Saved quotes and comparisons"}</li>
                  <li><AppIcon name="check" size={16} />{bn ? "Order ও payment tracking" : "Order and payment tracking"}</li>
                  <li><AppIcon name="check" size={16} />{bn ? "Delivery ও account notifications" : "Delivery and account notifications"}</li>
                </>}
              </ul>
            </div>
          </div>
          <div className="auth-login-brand__footer"><AppIcon name="shield" size={18} /><span><strong>{bn ? "Security by design" : "Security by design"}</strong><small>{bn ? "Encrypted session · Secure recovery" : "Protected sessions · Secure recovery"}</small></span></div>
        </aside>
        <form className="auth-login-form" name={`${portal}-login`} aria-labelledby="login-title" autoComplete="on" onSubmit={submit}>
          <header className="auth-login-form__header">
            <span className={`auth-portal-badge auth-portal-badge--${portal}`}><AppIcon name={portal === "admin" ? "shield" : "user"} size={15} />{portal === "admin" ? (bn ? "Admin portal" : "Admin portal") : (bn ? "Customer account" : "Customer account")}</span>
            <p className="eyebrow">{portal === "admin" ? (bn ? "Restricted access" : "Restricted access") : (bn ? "Welcome back" : "Welcome back")}</p>
            <h1 id="login-title">{portal === "admin" ? (bn ? "Admin sign in" : "Admin sign in") : (bn ? "SourceAI-এ sign in" : "Sign in to SourceAI")}</h1>
            <p>{portal === "admin" ? (bn ? "আপনার অনুমোদিত admin/operator credential ব্যবহার করুন।" : "Use your authorized admin or operator credentials.") : (bn ? "আপনার sourcing workspace-এ নিরাপদে ফিরে যান।" : "Continue securely to your sourcing workspace.")}</p>
          </header>
          {serviceState !== "ready" ? <div className={`auth-service-status auth-service-status--${serviceState}`} role="status">
            <span aria-hidden />
            <div>
              <strong>{serviceState === "checking" ? (bn ? "নিরাপদ সংযোগ যাচাই হচ্ছে…" : "Checking secure connection…") : (bn ? "Sign in service পাওয়া যাচ্ছে না" : "Sign-in service unavailable")}</strong>
              {serviceState === "offline" ? <small>{bn ? "আপনার credential ভুল নয়। সংযোগ ফিরে এলে আবার চেষ্টা করুন।" : "Your credentials were not rejected. Retry when the connection is restored."}</small> : null}
            </div>
            {serviceState === "offline" ? <button type="button" onClick={() => void checkService()}><AppIcon name="refresh" size={15} />{bn ? "Retry" : "Retry"}</button> : null}
          </div> : null}
          {portal === "customer" ? <>
            <button className="social-login-button" type="button" disabled={socialLoading || serviceState !== "ready"} onClick={async () => {
              setSocialLoading(true); setError("");
              try { await startGoogleLogin(); } catch (reason) {
                setError(isApiServiceUnavailable(reason)
                  ? loginErrorMessage(reason)
                  : reason instanceof Error ? reason.message : "Google login is unavailable.");
                setSocialLoading(false);
              }
            }}><GoogleIcon />{socialLoading ? (bn ? "Google-এ সংযোগ হচ্ছে…" : "Connecting to Google…") : (bn ? "Google দিয়ে চালিয়ে যান" : "Continue with Google")}</button>
            <div className="auth-divider"><span>{bn ? "অথবা email / account credential" : "or use email / account credentials"}</span></div>
          </> : null}
          <label className="auth-field" htmlFor="login-identifier"><span><AppIcon name="user" size={16} />{bn ? "Username, email অথবা phone" : "Username, email or phone"}</span><div className="auth-input"><input id="login-identifier" name="username" type="text" autoCapitalize="none" autoComplete="username" spellCheck={false} value={identifier} onChange={event => setIdentifier(event.target.value)} required /></div></label>
          <label className="auth-field" htmlFor="login-password"><span><AppIcon name="lock" size={16} />{bn ? "Password" : "Password"}</span><div className="auth-input"><input id="login-password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required /><button type="button" className="auth-password-toggle" aria-label={showPassword ? (bn ? "Password লুকান" : "Hide password") : (bn ? "Password দেখুন" : "Show password")} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}><AppIcon name={showPassword ? "eye-off" : "eye"} size={18} /></button></div></label>
          <div className="auth-login-options">
            <label className="remember-login"><input name="remember" type="checkbox" checked={remember} onChange={event => setRemember(event.target.checked)} /><span><strong>{bn ? "Sign in রাখা হবে" : "Keep me signed in"}</strong><small>{bn ? "এই device-এ ID মনে রাখুন" : "Remember my ID on this device"}</small></span></label>
            <Link href="/forgot-password">{bn ? "Password ভুলে গেছেন?" : "Forgot password?"}</Link>
          </div>
          {error ? <div className="form-error" role="alert">{error}</div> : null}
          {errorReference ? <small className="auth-error-reference">{bn ? "Support reference" : "Support reference"}: <code>{errorReference}</code></small> : null}
          <button className="market-button auth-submit" type="submit" disabled={loading || socialLoading || serviceState === "checking"}>{loading ? (bn ? "Sign in হচ্ছে…" : "Signing in…") : portal === "admin" ? <><AppIcon name="shield" size={18} />{bn ? "Admin dashboard খুলুন" : "Open admin dashboard"}</> : <><AppIcon name="lock" size={18} />{bn ? "নিরাপদে sign in" : "Sign in securely"}</>}</button>
          <footer className="auth-login-form__footer">
            {portal === "customer" ? <>
              <p>{bn ? "SourceAI-এ নতুন?" : "New to SourceAI?"} <Link href="/signup">{bn ? "Account তৈরি করুন" : "Create an account"}</Link></p>
              <Link className="auth-portal-link" href="/login?portal=admin" onClick={() => selectPortal("admin")}><AppIcon name="shield" size={16} /><span>{bn ? "Admin / operator access" : "Admin / operator access"}</span><AppIcon name="arrow-right" size={15} /></Link>
            </> : <>
              <p><AppIcon name="shield" size={15} />{bn ? "Password-এর পর MFA verification প্রয়োজন।" : "MFA verification follows password validation."}</p>
              <Link className="auth-portal-link" href="/login" onClick={() => selectPortal("customer")}><AppIcon name="arrow-left" size={15} /><span>{bn ? "Customer sign in-এ ফিরুন" : "Back to customer sign in"}</span></Link>
            </>}
          </footer>
        </form>
      </section>
    </main>
  );
}
