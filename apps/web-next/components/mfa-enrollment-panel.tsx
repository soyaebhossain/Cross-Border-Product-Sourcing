"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

type MfaEnrollmentPanelProps = {
  secret: string;
  otpauthUri: string;
  bn: boolean;
  generating: boolean;
  onGenerateNewQr: () => Promise<void>;
};

type CopyState = "idle" | "copied" | "failed";

export function MfaEnrollmentPanel({
  secret,
  otpauthUri,
  bn,
  generating,
  onGenerateNewQr,
}: MfaEnrollmentPanelProps) {
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const [confirmRotation, setConfirmRotation] = useState(false);
  const qrLabel = bn
    ? "Authenticator app দিয়ে QR code স্ক্যান করুন"
    : "Scan QR code with your authenticator app";

  useEffect(() => {
    setCopyState("idle");
    setConfirmRotation(false);
  }, [secret]);

  const copySetupKey = async () => {
    try {
      await navigator.clipboard.writeText(secret);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <section className="mfa-enrollment" aria-labelledby="mfa-enrollment-title">
      <header className="mfa-enrollment__header">
        <span className="mfa-enrollment__step">{bn ? "ধাপ ১" : "Step 1"}</span>
        <div>
          <h2 id="mfa-enrollment-title">{qrLabel}</h2>
          <p>
            {bn
              ? "Google Authenticator, Microsoft Authenticator বা অন্য কোনো TOTP app খুলে QR code-টি স্ক্যান করুন।"
              : "Open Google Authenticator, Microsoft Authenticator, or another TOTP app and scan this code."}
          </p>
        </div>
      </header>

      <div className="mfa-enrollment__grid">
        <figure className="mfa-qr">
          <div className="mfa-qr__surface">
            <QRCodeSVG
              value={otpauthUri}
              size={208}
              level="M"
              marginSize={4}
              role="img"
              aria-label={qrLabel}
              title={qrLabel}
            />
          </div>
          <figcaption>
            {bn
              ? "QR code-এ আপনার একবারের setup credential রয়েছে। এটি কারও সঙ্গে শেয়ার করবেন না।"
              : "This QR code contains your one-time setup credential. Do not share it with anyone."}
          </figcaption>
        </figure>

        <div className="mfa-enrollment__instructions">
          <span className="mfa-enrollment__step">{bn ? "ধাপ ২" : "Step 2"}</span>
          <h3>{bn ? "App-এ account যোগ করুন" : "Add the account in your app"}</h3>
          <ol>
            <li>{bn ? "App-এর QR scanner দিয়ে code-টি স্ক্যান করুন।" : "Scan the QR code with the app camera."}</li>
            <li>{bn ? "SourceAI account যোগ হয়েছে কি না নিশ্চিত করুন।" : "Confirm that the SourceAI account appears in the app."}</li>
            <li>{bn ? "বর্তমান ৬ সংখ্যার code নিচে লিখুন।" : "Enter the current six-digit code below."}</li>
          </ol>
          <a className="button button--ghost mfa-app-link" href={otpauthUri}>
            {bn ? "Authenticator app-এ খুলুন" : "Open in authenticator app"}
          </a>
        </div>
      </div>

      <details className="mfa-manual-setup">
        <summary>{bn ? "স্ক্যান করা যাচ্ছে না? Setup key ব্যবহার করুন" : "Can’t scan? Use a setup key"}</summary>
        <div className="mfa-manual-setup__content">
          <p>
            {bn
              ? "Authenticator app-এ manual entry বেছে নিয়ে নিচের key দিন। Account type হিসেবে Time based নির্বাচন করুন।"
              : "Choose manual entry in your authenticator app, enter this key, and select Time based as the account type."}
          </p>
          <div className="mfa-secret-row">
            <output className="mfa-secret" aria-label={bn ? "Authenticator setup key" : "Authenticator setup key"}>
              {secret}
            </output>
            <button className="button button--ghost" type="button" onClick={copySetupKey}>
              {bn ? "Setup key কপি করুন" : "Copy setup key"}
            </button>
          </div>
          <p className="mfa-copy-status" role="status" aria-live="polite">
            {copyState === "copied"
              ? (bn ? "Setup key কপি হয়েছে।" : "Setup key copied.")
              : copyState === "failed"
                ? (bn ? "কপি করা যায়নি। Key-টি ম্যানুয়ালি লিখুন।" : "Could not copy. Enter the key manually.")
                : ""}
          </p>
        </div>
      </details>

      <div className="mfa-rotate-setup">
        <div>
          <strong>{bn ? "QR code বা setup key প্রকাশ হয়ে গেছে?" : "Was the QR code or setup key exposed?"}</strong>
          <p>
            {bn
              ? "নতুন QR code তৈরি করলে বর্তমান code ও key সঙ্গে সঙ্গে কাজ করা বন্ধ করবে।"
              : "Generate a fresh QR code if this one was shared or shown. The current QR code and key will stop working immediately."}
          </p>
        </div>
        {!confirmRotation ? (
          <button className="auth-text-button mfa-rotate-setup__trigger" type="button" onClick={() => setConfirmRotation(true)}>
            {bn ? "নতুন QR code তৈরি করুন" : "Generate a new QR code"}
          </button>
        ) : (
          <div className="mfa-rotate-confirm" role="group" aria-label={bn ? "নতুন QR code তৈরির অনুমোদন" : "Confirm new QR code generation"}>
            <p>{bn ? "বর্তমান QR code বাতিল করে নতুনটি তৈরি করবেন?" : "Replace the current QR code with a new one?"}</p>
            <div>
              <button
                className="button button--ghost mfa-rotate-confirm__confirm"
                type="button"
                disabled={generating}
                onClick={async () => {
                  await onGenerateNewQr();
                  setConfirmRotation(false);
                }}
              >
                {generating ? (bn ? "তৈরি হচ্ছে…" : "Generating…") : (bn ? "হ্যাঁ, নতুন QR code তৈরি করুন" : "Yes, generate new QR code")}
              </button>
              <button className="button button--ghost" type="button" disabled={generating} onClick={() => setConfirmRotation(false)}>
                {bn ? "বর্তমান QR code রাখুন" : "Keep current QR code"}
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
