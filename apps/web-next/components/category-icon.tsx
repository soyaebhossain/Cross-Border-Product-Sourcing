type CategoryIconProps = {
  name: string;
};

function categoryKind(name: string) {
  const value = name.toLowerCase();
  if (
    (value.includes("mobile") || value.includes("phone")) &&
    value.includes("accessor")
  ) return "mobile-accessories";
  if (
    (value.includes("laptop") || value.includes("pc")) &&
    value.includes("accessor")
  ) return "laptop-accessories";
  if (value.includes("education") || value.includes("academic")) return "education";
  if (value.includes("creator") || value.includes("content tool")) return "creator";
  if (value.includes("packaging") || value.includes("e-commerce")) return "packaging";
  if (value.includes("organization") || value.includes("organizer") || value.includes("storage")) return "storage";
  if (value.includes("fashion")) return "fashion";
  if (value.includes("beauty") && (value.includes("tool") || value.includes("accessor"))) return "beauty-tools";
  if (value.includes("kitchen")) return "kitchen";
  if (value.includes("office") || value.includes("desk accessor")) return "office";
  if (value.includes("travel") || value.includes("luggage")) return "travel";
  if (value.includes("pet care") || value.includes("pet accessor")) return "pet";
  if (
    value.includes("jewel") ||
    value.includes("precious") ||
    value.includes("gem") ||
    value.includes("gold") ||
    value.includes("silver") ||
    value.includes("diamond") ||
    value.includes("bullion")
  ) return "jewelry";
  if (value.includes("3d") || value.includes("printing")) return "printing";
  if (value.includes("agri") || value.includes("farm")) return "agriculture";
  if (value.includes("energy") || value.includes("ev")) return "energy";
  if (value.includes("cosmetic") || value.includes("beauty")) return "cosmetics";
  if (value.includes("electronic")) return "electronics";
  if (value.includes("fan") || value.includes("cooling")) return "fan";
  if (value.includes("hair")) return "haircare";
  if (value.includes("industrial") || value.includes("automation")) return "automation";
  if (value.includes("medical") || value.includes("health")) return "medical";
  if (value.includes("component") || value.includes("computer") || value.includes("pc ")) return "components";
  if (value.includes("phone") || value.includes("mobile")) return "phones";
  if (value.includes("scientific") || value.includes("instrument") || value.includes("laboratory")) return "scientific";
  if (value.includes("skin")) return "skincare";
  return "general";
}

export function CategoryIcon({ name }: CategoryIconProps) {
  const kind = categoryKind(name);
  return (
    <span className={`category-icon category-icon--${kind}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        {kind === "mobile-accessories" ? <>
          <rect x="5" y="3.5" width="14" height="25" rx="2.8" />
          <path d="M10 7h4M10.5 25h3" />
          <path d="M23 16v3m4-3v3M22 19h6v4a3 3 0 0 1-3 3h-1a3 3 0 0 1-3-3v-4h1Z" />
        </> : null}
        {kind === "laptop-accessories" ? <>
          <path d="M6 6h20v16H6zM3.5 26h25l-2.5-4H6z" />
          <path d="M11 11h10M11 15h6M23 11v6" />
        </> : null}
        {kind === "education" ? <>
          <path d="m3 11 13-7 13 7-13 7z" />
          <path d="M8 14.5V21c4.8 3.8 11.2 3.8 16 0v-6.5M28 12v9" />
        </> : null}
        {kind === "creator" ? <>
          <rect x="4" y="8" width="24" height="18" rx="3" />
          <path d="m10 8 2.5-4h7L22 8M14 13l6 4-6 4z" />
        </> : null}
        {kind === "packaging" ? <>
          <path d="m5 10 11-6 11 6-11 6zM5 10v13l11 6 11-6V10M16 16v13" />
          <path d="m11 7 11 6v6l-3-1.5-3 1.5" />
        </> : null}
        {kind === "storage" ? <>
          <rect x="4" y="5" width="24" height="22" rx="2.5" />
          <path d="M4 13h24M4 21h24M13 9h6M13 17h6M13 25h6" />
        </> : null}
        {kind === "fashion" ? <>
          <path d="M6 11h20l2 17H4z" />
          <path d="M11 11V9a5 5 0 0 1 10 0v2M9 17h14" />
        </> : null}
        {kind === "beauty-tools" ? <>
          <circle cx="11" cy="11" r="6.5" />
          <path d="M11 17.5V28M7 28h8M23 5l4 4-7.5 13.5-5 2 1.5-5zM20.5 7.5l4 4" />
        </> : null}
        {kind === "kitchen" ? <>
          <path d="M7 4v7m-3-7v6c0 3 6 3 6 0V4M7 13v15" />
          <path d="M21 4c-3 0-5 3.2-5 7s2 6 5 6 5-2.2 5-6-2-7-5-7ZM21 17v11" />
        </> : null}
        {kind === "office" ? <>
          <path d="M7 4h13l5 5v19H7zM20 4v6h5" />
          <path d="M11 15h10M11 20h10M11 25h6" />
        </> : null}
        {kind === "travel" ? <>
          <path d="M11 8V5h10v3M7 8h18v20H7zM12 13v10M20 13v10M11 28v2M21 28v2" />
        </> : null}
        {kind === "pet" ? <>
          <circle cx="8" cy="10" r="2.7" />
          <circle cx="14" cy="6.5" r="2.7" />
          <circle cx="21" cy="7" r="2.7" />
          <circle cx="26" cy="12" r="2.7" />
          <path d="M8.5 23.5c0-4.8 3.3-8.5 7.5-8.5s7.5 3.7 7.5 8.5c0 2.9-2.4 4.3-4.8 3l-2.7-1.4-2.7 1.4c-2.4 1.3-4.8-.1-4.8-3Z" />
        </> : null}
        {kind === "jewelry" ? <>
          <path d="m6 12 5-7h10l5 7-10 15z" />
          <path d="M6 12h20M11 5l5 7 5-7M16 12v15" />
        </> : null}
        {kind === "printing" ? <>
          <path d="M7 5h18v7H7zM10 12v4m12-4v4M6 27h20M9 16h14v8H9z" />
          <path d="m16 16 4 2.3V23l-4 2.2-4-2.2v-4.7zM16 16v4.7m4-2.4-4 2.4-4-2.4" />
        </> : null}
        {kind === "agriculture" ? <>
          <path d="M16 27V14M16 18c-5.8 0-9-3.3-9-9 5.8 0 9 3.3 9 9ZM16 14c0-5.4 3.2-8.4 9-8.4 0 5.4-3.2 8.4-9 8.4Z" />
          <path d="M8 27h16" />
        </> : null}
        {kind === "energy" ? <>
          <path d="m18 3-9 14h7l-2 12 9-15h-7z" />
          <path d="M5 24c2.7-.2 4.8.7 6.2 2.7" />
        </> : null}
        {kind === "cosmetics" ? <>
          <path d="M11 11h10v16H11zM13 5h6v6h-6zM13 16h6" />
          <path d="M22.5 8.5c1.8 2 2.5 3.5 2.5 4.7a2.5 2.5 0 0 1-5 0c0-1.2.7-2.7 2.5-4.7Z" />
        </> : null}
        {kind === "electronics" ? <>
          <rect x="9" y="9" width="14" height="14" rx="2" />
          <path d="M13 13h6v6h-6zM12 4v5m8-5v5M12 23v5m8-5v5M4 12h5m-5 8h5m14-8h5m-5 8h5" />
        </> : null}
        {kind === "fan" ? <>
          <circle cx="16" cy="16" r="2.4" />
          <path d="M16 13.6c-2.2-2.8-2-6.2.6-8.6 3.1 2.3 3.4 5.6 1.6 8.9M18.2 17.1c3.5-.5 6.3 1.3 7 4.8-3.5 1.6-6.5.2-8.2-2.8M13.8 17.1c-1.3 3.3-4.3 4.8-7.6 3.7.5-3.8 3.2-5.7 6.7-5.4" />
        </> : null}
        {kind === "haircare" ? <>
          <path d="M7 11h12a5 5 0 0 1 0 10H7zM7 13v6M20 13l6-3v12l-6-3M12 21v6m4-6v6" />
        </> : null}
        {kind === "automation" ? <>
          <path d="M7 27h18M10 27v-5h5l3-5-4-3 3-5 5 3-2 5 4 3v7" />
          <circle cx="17" cy="9" r="2.5" />
          <path d="M8 8h4v4H8z" />
        </> : null}
        {kind === "medical" ? <>
          <path d="M12 5h8v7h7v8h-7v7h-8v-7H5v-8h7z" />
          <path d="M23 5c2.2 0 4 1.8 4 4" />
        </> : null}
        {kind === "components" ? <>
          <rect x="8" y="8" width="16" height="16" rx="2" />
          <path d="M12 12h8v8h-8zM12 3v5m8-5v5M12 24v5m8-5v5M3 12h5m-5 8h5m16-8h5m-5 8h5" />
        </> : null}
        {kind === "phones" ? <>
          <rect x="9" y="3.5" width="14" height="25" rx="3" />
          <path d="M13 7h6M14 24.5h4" />
        </> : null}
        {kind === "scientific" ? <>
          <path d="M12 4h8M13 4v9L7 24a2.7 2.7 0 0 0 2.4 4h13.2a2.7 2.7 0 0 0 2.4-4l-6-11V4" />
          <path d="M10.5 21h11M13 17h6" />
        </> : null}
        {kind === "skincare" ? <>
          <path d="M12 8h8M13 4h6v4M10 8h12l2 19H8z" />
          <path d="M12.5 16c2-2.5 5-2.5 7 0-1.3 3.2-5.7 3.2-7 0Z" />
        </> : null}
        {kind === "general" ? <>
          <path d="m16 4 11 6-11 6L5 10zM5 10v12l11 6 11-6V10M16 16v12" />
        </> : null}
      </svg>
    </span>
  );
}
