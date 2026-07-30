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
    (value.includes("mobile") || value.includes("phone")) &&
    value.includes("accessor")
  ) {
    return {
      accent: "#1d4ed8",
      soft: "#dbeafe",
      icon:
        '<rect x="18" y="7" width="53" height="106" rx="10"/><path d="M37 22h16M39 97h12M88 62v13m18-13v13M83 75h28v15c0 12-8 21-19 21h-1c-11 0-19-9-19-21V75h11"/>',
    };
  }

  if (
    (value.includes("laptop") || value.includes("pc")) &&
    value.includes("accessor")
  ) {
    return {
      accent: "#4338ca",
      soft: "#e0e7ff",
      icon:
        '<path d="M17 16h86v62H17ZM6 98h108l-11-20H17Z"/><path d="M38 37h44M38 52h26M91 36v24"/>',
    };
  }

  if (value.includes("education") || value.includes("academic")) {
    return {
      accent: "#7e22ce",
      soft: "#f3e8ff",
      icon:
        '<path d="m8 41 52-29 52 29-52 29Z"/><path d="M27 57v26c19 15 47 15 66 0V57M108 47v39"/>',
    };
  }

  if (value.includes("creator") || value.includes("content tool")) {
    return {
      accent: "#be123c",
      soft: "#ffe4e6",
      icon:
        '<rect x="8" y="30" width="104" height="76" rx="14"/><path d="m35 30 11-18h29l11 18M51 50l27 18-27 18Z"/>',
    };
  }

  if (value.includes("packaging") || value.includes("e-commerce")) {
    return {
      accent: "#b45309",
      soft: "#fef3c7",
      icon:
        '<path d="m12 39 48-27 48 27-48 28Z"/><path d="M12 39v55l48 26 48-26V39M60 67v53M39 25l47 28v25l-13-7-13 7"/>',
    };
  }

  if (
    value.includes("organization") ||
    value.includes("organizer") ||
    value.includes("storage")
  ) {
    return {
      accent: "#0f766e",
      soft: "#ccfbf1",
      icon:
        '<rect x="10" y="9" width="100" height="102" rx="10"/><path d="M10 43h100M10 77h100M47 26h26M47 60h26M47 94h26"/>',
    };
  }

  if (value.includes("fashion")) {
    return {
      accent: "#a21caf",
      soft: "#fae8ff",
      icon:
        '<path d="M18 40h84l10 72H8Z"/><path d="M39 40v-8c0-15 9-24 21-24s21 9 21 24v8M31 65h58"/>',
    };
  }

  if (value.includes("beauty") && (value.includes("tool") || value.includes("accessor"))) {
    return {
      accent: "#be185d",
      soft: "#fce7f3",
      icon:
        '<circle cx="40" cy="39" r="27"/><path d="M40 66v46M24 112h32M90 13l17 17-31 57-20 8 7-21ZM80 23l17 17"/>',
    };
  }

  if (value.includes("kitchen")) {
    return {
      accent: "#c2410c",
      soft: "#ffedd5",
      icon:
        '<path d="M27 8v30M13 8v26c0 13 28 13 28 0V8M27 47v65"/><path d="M84 8c-13 0-21 14-21 30s8 26 21 26 21-10 21-26S97 8 84 8ZM84 64v48"/>',
    };
  }

  if (value.includes("office") || value.includes("desk accessor")) {
    return {
      accent: "#475569",
      soft: "#e2e8f0",
      icon:
        '<path d="M21 8h57l21 21v83H21ZM78 8v25h21"/><path d="M39 55h43M39 76h43M39 97h27"/>',
    };
  }

  if (value.includes("travel") || value.includes("luggage")) {
    return {
      accent: "#0369a1",
      soft: "#e0f2fe",
      icon:
        '<path d="M40 26V10h40v16M22 26h76v86H22ZM43 48v42M77 48v42M40 112v8M80 112v8"/>',
    };
  }

  if (value.includes("pet care") || value.includes("pet accessor")) {
    return {
      accent: "#047857",
      soft: "#d1fae5",
      icon:
        '<circle cx="24" cy="37" r="12"/><circle cx="49" cy="20" r="12"/><circle cx="78" cy="22" r="12"/><circle cx="100" cy="44" r="12"/><path d="M26 91c0-21 15-38 34-38s34 17 34 38c0 13-11 19-22 14l-12-7-12 7c-11 5-22-1-22-14Z"/>',
    };
  }

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
