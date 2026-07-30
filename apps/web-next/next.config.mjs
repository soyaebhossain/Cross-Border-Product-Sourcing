import path from "node:path";

const isProduction = process.env.NODE_ENV === "production";
const isVercelProduction = process.env.VERCEL_ENV === "production";
const productionApiOrigin = "https://cross-border-product-sourcing-api.onrender.com";

function normalizedApiOrigin(value) {
  if (!value) return "";
  const parsed = new URL(value);
  const localHttpHosts = new Set(["api", "localhost", "127.0.0.1", "::1"]);
  const permitsHttp = parsed.protocol === "http:"
    && (!isProduction || localHttpHosts.has(parsed.hostname));
  if (
    (parsed.protocol !== "https:" && !permitsHttp)
    || parsed.username
    || parsed.password
    || parsed.search
    || parsed.hash
    || !["", "/"].includes(parsed.pathname)
  ) {
    throw new Error("API base URL must be a root HTTP(S) origin without credentials, query, or fragment");
  }
  return parsed.origin;
}

const defaultApiOrigin = isVercelProduction
  ? productionApiOrigin
  : isProduction
    ? ""
    : "http://localhost:8001";
const apiProxyOrigin = normalizedApiOrigin(
  isVercelProduction ? productionApiOrigin : process.env.API_BASE_URL || defaultApiOrigin,
);

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  "img-src 'self' data: blob: http: https:",
  "connect-src 'self'",
  "frame-src https://accounts.google.com",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  { key: "Cross-Origin-Resource-Policy", value: "same-site" },
  ...(isProduction
    ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]
    : []),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  typedRoutes: true,
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  poweredByHeader: false,
  skipTrailingSlashRedirect: true,
  async rewrites() {
    if (!apiProxyOrigin) return [];
    return [
      {
        source: "/api/:path*/",
        destination: `${apiProxyOrigin}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${apiProxyOrigin}/api/:path*`,
      },
      {
        source: "/media/:path*",
        destination: `${apiProxyOrigin}/media/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
