"use client";

import { useEffect, useState } from "react";
import { useLocale } from "../lib/locale-context";

export function PaymentProofPreview({ src, label }: { src?: string | null; label?: string }) {
  const [failed, setFailed] = useState(false);
  const { locale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => setFailed(false), [src]);

  if (!src) {
    return <div className="admin-proof-state" role="status"><strong>{bn ? "Payment proof নেই" : "No payment proof"}</strong><span>{bn ? "Customer এখনো কোনো proof URL জমা দেয়নি।" : "The customer has not submitted a proof URL."}</span></div>;
  }

  return <div className="admin-proof-preview">
    {!failed ? <>
      {/* Payment evidence may use a protected API/media origin, so it is intentionally rendered without the Next image loader. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={label || (bn ? "জমা দেওয়া payment proof" : "Submitted payment proof")} loading="lazy" decoding="async" onError={() => setFailed(true)} />
    </> : <div className="admin-proof-state" role="status"><strong>{bn ? "Inline preview পাওয়া যায়নি" : "Inline preview unavailable"}</strong><span>{bn ? "ফাইলটি image নয়, মেয়াদ শেষ, অথবা media origin access বন্ধ হতে পারে। নিচের secure link ব্যবহার করুন।" : "The file may not be an image, may have expired, or its media origin may deny inline access. Use the secure link below."}</span></div>}
    <div className="admin-proof-preview__actions"><a className="admin-row-button" href={src} target="_blank" rel="noreferrer">{bn ? "নতুন tab-এ খুলুন" : "Open in new tab"}</a><a className="admin-row-button" href={src} download>{bn ? "ডাউনলোড চেষ্টা করুন" : "Download proof"}</a></div>
  </div>;
}
