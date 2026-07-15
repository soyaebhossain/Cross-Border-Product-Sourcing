"use client";
import { useEffect, useState } from "react";

function fallbackDataUrl(name: string, category?: string) {
  const initials = name.split(/\s+/).slice(0, 2).map(part => part[0] || "").join("").toUpperCase();
  const label = (category || "Sourcing product").slice(0, 28);
  const safe = (value: string) => value.replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[char] || char));
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#dbeafe"/><stop offset="1" stop-color="#e2e8f0"/></linearGradient></defs><rect width="640" height="480" fill="url(#g)"/><circle cx="320" cy="205" r="92" fill="#fff" opacity=".82"/><text x="320" y="226" text-anchor="middle" font-family="Arial,sans-serif" font-size="64" font-weight="700" fill="#2563eb">${safe(initials || "SA")}</text><text x="320" y="340" text-anchor="middle" font-family="Arial,sans-serif" font-size="22" font-weight="600" fill="#334155">${safe(label)}</text><text x="320" y="374" text-anchor="middle" font-family="Arial,sans-serif" font-size="15" fill="#64748b">SourceAI verified catalog</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export function ProductImage({ src, name, category, className }: { src?: string | null; name: string; category?: string; className?: string }) {
  const fallback = fallbackDataUrl(name, category); const preferred = src || fallback; const [current, setCurrent] = useState(preferred);
  useEffect(() => setCurrent(preferred), [preferred]);
  return <img className={className} src={current} alt={name} loading="lazy" decoding="async" onError={() => { if (current !== fallback) setCurrent(fallback); }} />;
}
