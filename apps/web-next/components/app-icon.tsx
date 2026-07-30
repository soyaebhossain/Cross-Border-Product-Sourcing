import type { SVGProps } from "react";

export type AppIconName =
  | "alert"
  | "arrow-left"
  | "arrow-right"
  | "check"
  | "chevron-down"
  | "close"
  | "eye"
  | "eye-off"
  | "globe"
  | "grid"
  | "language"
  | "lock"
  | "logout"
  | "menu"
  | "orders"
  | "package"
  | "refresh"
  | "search"
  | "shield"
  | "user";

type AppIconProps = SVGProps<SVGSVGElement> & {
  name: AppIconName;
  size?: number;
};

const paths: Record<AppIconName, React.ReactNode> = {
  alert: <>
    <path d="M12 3.4 2.9 19.2a1.2 1.2 0 0 0 1 1.8h16.2a1.2 1.2 0 0 0 1-1.8L12 3.4Z" />
    <path d="M12 9v4.7M12 17.3h.01" />
  </>,
  "arrow-left": <path d="m15 18-6-6 6-6M9 12h11" />,
  "arrow-right": <path d="m9 18 6-6-6-6M4 12h11" />,
  check: <path d="m5 12.5 4.2 4.2L19.5 6.5" />,
  "chevron-down": <path d="m7 10 5 5 5-5" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  eye: <>
    <path d="M2.8 12s3.3-5.3 9.2-5.3 9.2 5.3 9.2 5.3-3.3 5.3-9.2 5.3S2.8 12 2.8 12Z" />
    <circle cx="12" cy="12" r="2.4" />
  </>,
  "eye-off": <>
    <path d="m4 4 16 16M9.5 7A9.6 9.6 0 0 1 12 6.7c5.9 0 9.2 5.3 9.2 5.3a15 15 0 0 1-2.3 2.8M6.3 8.4A15.2 15.2 0 0 0 2.8 12s3.3 5.3 9.2 5.3a9 9 0 0 0 3-.5M10.4 10.4a2.3 2.3 0 0 0 3.2 3.2" />
  </>,
  globe: <>
    <circle cx="12" cy="12" r="9" />
    <path d="M3.5 12h17M12 3c2.1 2.4 3.2 5.4 3.2 9S14.1 18.6 12 21M12 3C9.9 5.4 8.8 8.4 8.8 12s1.1 6.6 3.2 9" />
  </>,
  grid: <>
    <rect x="4" y="4" width="6" height="6" rx="1" />
    <rect x="14" y="4" width="6" height="6" rx="1" />
    <rect x="4" y="14" width="6" height="6" rx="1" />
    <rect x="14" y="14" width="6" height="6" rx="1" />
  </>,
  language: <>
    <circle cx="12" cy="12" r="9" />
    <path d="M3.5 12h17M12 3c2.1 2.4 3.2 5.4 3.2 9S14.1 18.6 12 21M12 3C9.9 5.4 8.8 8.4 8.8 12s1.1 6.6 3.2 9" />
  </>,
  lock: <>
    <rect x="5" y="10" width="14" height="10" rx="2" />
    <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10M12 14v2" />
  </>,
  logout: <path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  orders: <>
    <path d="M7 4h10v3H7zM6 7h12v14H6z" />
    <path d="M9 11h6M9 15h6M9 18h4" />
  </>,
  package: <>
    <path d="m12 3 8 4.4v9.2L12 21l-8-4.4V7.4L12 3Z" />
    <path d="m4.3 7.5 7.7 4.3 7.7-4.3M12 11.8V21M8 5.2l8 4.5" />
  </>,
  refresh: <path d="M20 7v5h-5M4 17v-5h5M18.2 9A7 7 0 0 0 6.6 6.4L4 9M5.8 15A7 7 0 0 0 17.4 17.6L20 15" />,
  search: <>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </>,
  shield: <>
    <path d="M12 3 20 6v5.5c0 4.7-3.1 7.8-8 9.5-4.9-1.7-8-4.8-8-9.5V6l8-3Z" />
    <path d="m8.5 12 2.2 2.2 4.8-4.8" />
  </>,
  user: <>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20c.6-4 3-6 7-6s6.4 2 7 6" />
  </>,
};

export function AppIcon({
  name,
  size = 20,
  className,
  ...props
}: AppIconProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      focusable="false"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      width={size}
      {...props}
    >
      {paths[name]}
    </svg>
  );
}

export function GoogleIcon({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      focusable="false"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      <path d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.9h5.4a4.6 4.6 0 0 1-2 3v2.6h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z" fill="#4285F4" />
      <path d="M12 22c2.7 0 5-.9 6.7-2.3l-3.3-2.6c-.9.6-2.1 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3v2.7A10 10 0 0 0 12 22Z" fill="#34A853" />
      <path d="M6.4 14a6 6 0 0 1 0-3.9V7.4H3a10 10 0 0 0 0 9.3L6.4 14Z" fill="#FBBC05" />
      <path d="M12 5.9c1.5 0 2.8.5 3.9 1.5l2.9-2.9A9.7 9.7 0 0 0 12 2a10 10 0 0 0-9 5.4l3.4 2.7C7.2 7.7 9.4 6 12 6Z" fill="#EA4335" />
    </svg>
  );
}
