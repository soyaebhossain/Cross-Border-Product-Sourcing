import { NextRequest, NextResponse } from "next/server";

const CLIENT_IP_HEADER = "x-sourceai-client-ip";
const TIMESTAMP_HEADER = "x-sourceai-proxy-timestamp";
const SIGNATURE_HEADER = "x-sourceai-proxy-signature";

function hex(buffer: ArrayBuffer) {
  return Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2, "0")).join("");
}

async function signature(secret: string, payload: string) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(payload)));
}

export async function middleware(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.delete(CLIENT_IP_HEADER);
  requestHeaders.delete(TIMESTAMP_HEADER);
  requestHeaders.delete(SIGNATURE_HEADER);

  const secret = process.env.API_PROXY_SHARED_SECRET?.trim();
  const vercelClientIp = process.env.VERCEL
    ? request.headers.get("x-vercel-forwarded-for")?.trim()
    : null;
  if (secret && secret.length >= 32 && vercelClientIp) {
    const clientIp = vercelClientIp.split(",", 1)[0].trim();
    const timestamp = Math.floor(Date.now() / 1000).toString();
    requestHeaders.set(CLIENT_IP_HEADER, clientIp);
    requestHeaders.set(TIMESTAMP_HEADER, timestamp);
    requestHeaders.set(
      SIGNATURE_HEADER,
      await signature(secret, `${clientIp}\n${timestamp}`),
    );
  }

  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  matcher: "/api/:path*",
};
