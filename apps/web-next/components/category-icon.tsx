type CategoryIconProps = {
  name: string;
};

function categoryKind(name: string) {
  const value = name.toLowerCase();
  if (value.includes("3d") || value.includes("printing")) return "printing";
  if (value.includes("agri") || value.includes("farm")) return "agriculture";
  if (value.includes("energy") || value.includes("ev")) return "energy";
  if (value.includes("cosmetic") || value.includes("beauty")) return "cosmetics";
  if (value.includes("electronic")) return "electronics";
  if (value.includes("fan") || value.includes("cooling")) return "fan";
  if (value.includes("hair")) return "haircare";
  if (value.includes("industrial") || value.includes("automation")) return "automation";
  if (value.includes("medical") || value.includes("health")) return "medical";
  return "general";
}

export function CategoryIcon({ name }: CategoryIconProps) {
  const kind = categoryKind(name);
  return (
    <span className={`category-icon category-icon--${kind}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
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
        {kind === "general" ? <>
          <path d="m16 4 11 6-11 6L5 10zM5 10v12l11 6 11-6V10M16 16v12" />
        </> : null}
      </svg>
    </span>
  );
}
