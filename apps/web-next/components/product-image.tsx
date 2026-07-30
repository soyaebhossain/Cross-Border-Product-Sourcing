"use client";
import { useEffect, useState } from "react";

type CategoryVisual = {
  accent: string;
  soft: string;
  icon: string;
};

function categoryVisual(category?: string): CategoryVisual {
  const value = (category || "").toLowerCase();

  if (
    value.includes("jewel") ||
    value.includes("precious") ||
    value.includes("gem") ||
    value.includes("gold") ||
    value.includes("silver") ||
    value.includes("diamond") ||
    value.includes("bullion")
  ) {
    return {
      accent: "#a16207",
      soft: "#fef3c7",
      icon:
        '<path d="m14 42 20-28h52l20 28-46 66Z"/><path d="M14 42h92M34 14l26 28 26-28M60 42v66"/>',
    };
  }

  if (value.includes("medical") || value.includes("health")) {
    return {
      accent: "#059669",
      soft: "#d1fae5",
      icon: '<path d="M45 10h30v35h35v30H75v35H45V75H10V45h35Z"/>',
    };
  }

  if (value.includes("agri") || value.includes("farm")) {
    return {
      accent: "#16a34a",
      soft: "#dcfce7",
      icon:
        '<path d="M60 110V50M60 72C30 72 14 55 14 25c30 0 46 17 46 47ZM60 50c0-27 16-42 46-42 0 27-16 42-46 42ZM20 110h80"/>',
    };
  }

  if (value.includes("energy") || value.includes("ev")) {
    return {
      accent: "#d97706",
      soft: "#fef3c7",
      icon: '<path d="m72 6-46 70h36l-10 40 46-74H63Z"/>',
    };
  }

  if (
    value.includes("cosmetic") ||
    value.includes("beauty") ||
    value.includes("hair") ||
    value.includes("skin")
  ) {
    return {
      accent: "#db2777",
      soft: "#fce7f3",
      icon:
        '<path d="M40 32h40M48 32V16h24v16M36 42h48v66H36Z"/><path d="M48 58h24M60 70v22"/>',
    };
  }

  if (value.includes("fan") || value.includes("ventilation")) {
    return {
      accent: "#0284c7",
      soft: "#e0f2fe",
      icon:
        '<circle cx="60" cy="60" r="10"/><path d="M60 50C45 28 52 10 66 10c17 0 20 25 4 44M70 60c26-4 39 11 32 24-8 15-31 6-37-14M60 70c-11 24-31 27-39 14-9-14 10-30 34-24"/>',
    };
  }

  if (value.includes("industrial") || value.includes("automation")) {
    return {
      accent: "#475569",
      soft: "#e2e8f0",
      icon:
        '<path d="M22 104h76M34 104V80h18l8-18 18 18h10v24"/><circle cx="60" cy="44" r="18"/><path d="M60 20V8M60 80v-8M36 44H24M96 44H84M43 27l-9-9M86 70l-9-9M77 27l9-9M34 70l9-9"/>',
    };
  }

  if (value.includes("3d") || value.includes("print")) {
    return {
      accent: "#7c3aed",
      soft: "#ede9fe",
      icon:
        '<path d="M20 18h80v84H20Z"/><path d="M34 34h52v38H34ZM42 88h36M60 72v16"/><path d="m48 52 12-7 12 7v13l-12 7-12-7Z"/>',
    };
  }

  if (value.includes("phone") || value.includes("mobile")) {
    return {
      accent: "#2563eb",
      soft: "#dbeafe",
      icon:
        '<rect x="32" y="8" width="56" height="104" rx="10"/><path d="M48 24h24M52 94h16"/>',
    };
  }

  if (value.includes("electronic") || value.includes("component") || value.includes("computer")) {
    return {
      accent: "#2563eb",
      soft: "#dbeafe",
      icon:
        '<rect x="30" y="30" width="60" height="60" rx="8"/><path d="M48 48h24v24H48ZM42 18v12M60 18v12M78 18v12M42 90v12M60 90v12M78 90v12M18 42h12M18 60h12M18 78h12M90 42h12M90 60h12M90 78h12"/>',
    };
  }

  if (value.includes("scientific") || value.includes("instrument")) {
    return {
      accent: "#0891b2",
      soft: "#cffafe",
      icon:
        '<path d="M45 12h30M50 12v36L22 98c-4 8 2 14 11 14h54c9 0 15-6 11-14L70 48V12"/><path d="M36 82h48M46 66h28"/>',
    };
  }

  return {
    accent: "#2563eb",
    soft: "#dbeafe",
    icon:
      '<path d="m20 38 40-22 40 22v46l-40 22-40-22Z"/><path d="m20 38 40 22 40-22M60 60v46M40 27l40 22"/>',
  };
}

function fallbackDataUrl(category?: string) {
  const { accent, soft, icon } = categoryVisual(category);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f8fafc"/><stop offset="1" stop-color="${soft}"/></linearGradient></defs><rect width="640" height="480" rx="32" fill="url(#bg)"/><circle cx="320" cy="232" r="126" fill="#fff" opacity=".94"/><circle cx="320" cy="232" r="126" fill="none" stroke="${accent}" stroke-opacity=".12" stroke-width="4"/><g transform="translate(260 172)" fill="none" stroke="${accent}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round">${icon}</g><path d="M100 96h74M466 384h74" stroke="${accent}" stroke-opacity=".22" stroke-width="10" stroke-linecap="round"/><circle cx="116" cy="384" r="18" fill="${accent}" opacity=".12"/><circle cx="524" cy="96" r="18" fill="${accent}" opacity=".12"/></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export function ProductImage({ src, name, category, className }: { src?: string | null; name: string; category?: string; className?: string }) {
  const fallback = fallbackDataUrl(category); const preferred = src || fallback; const [current, setCurrent] = useState(preferred);
  useEffect(() => setCurrent(preferred), [preferred]);
  // Remote supplier URLs and inline generated fallbacks are intentionally rendered without a Next image loader.
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={className} src={current} alt={name} loading="lazy" decoding="async" onError={() => { if (current !== fallback) setCurrent(fallback); }} />;
}
