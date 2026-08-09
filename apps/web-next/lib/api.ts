export type Category = {
  id: number;
  name: string;
  slug: string;
};

export type ProductVariant = {
  id: number;
  sku: string | null;
  variant_name: string | null;
  weight_kg: string;
  length_cm: string;
  width_cm: string;
  height_cm: string;
};

export type ProductMediaKind = "supplier" | "reference" | "illustrative";

export type ProductMedia = {
  id?: number | string;
  src?: string | null;
  url?: string | null;
  image?: string | null;
  alt?: string | null;
  kind?: ProductMediaKind | string | null;
  source?: ProductMediaKind | string | null;
  verified?: boolean | null;
  is_primary?: boolean | null;
};

export type ProductImageMetadata = {
  url?: string | null;
  alt?: string | null;
  kind?: ProductMediaKind | "owned" | "external" | "fallback" | string | null;
  credit?: string | null;
};

export type ResolvedProductMedia = {
  key: string;
  src: string | null;
  alt: string;
  kind: ProductMediaKind;
  verified: boolean;
};

export type Product = {
  id: number;
  name: string;
  slug: string;
  model: string | null;
  description: string | null;
  image: string | null;
  image_alt?: string | null;
  image_source?: ProductMediaKind | string | null;
  image_verified?: boolean | null;
  images?: ProductMedia[] | null;
  image_metadata?: ProductImageMetadata | null;
  category: Category;
  variants: ProductVariant[];
  default_variant_id: number | null;
  market?: { min_price?: number; currency?: string; max_rating?: number; min_delivery_days?: number; risk_level?: string; supplier_count?: number; countries?: string[]; recommended_score?: number };
  catalog_source?: "snapshot";
};

export type Country = {
  id: number;
  code: string;
  name: string;
};

export type QuoteResponse = {
  offers_top?: Array<{
    id: number;
    seller: string;
    price_origin: string;
    currency: string;
    stock: number;
    rating: string;
    moq: number;
  }>;
  selected_offer_id?: number;
  breakdown?: {
    product_cost_bdt: string;
    origin_price_bdt: string;
    shipping_bdt: string;
    customs_duty_bdt: string;
    vat_tax_bdt: string;
    handling_charge_bdt: string;
    other_import_cost_bdt: string;
    duty_vat_bdt: string;
    service_fee_bdt: string;
    total_bdt: string;
    advance_bdt: string;
    remaining_bdt: string;
  };
  eta?: {
    min_days: number;
    max_days: number;
  };
  ai_explanation?: {
    summary_bn: string;
    advantages: string[];
    risks: string[];
    missing_information: string[];
    recommended_checks: string[];
    confidence: number | null;
    human_review_required: boolean;
  };
  ai_metadata?: {
    source: "ollama-via-n8n" | "deterministic-fallback" | string;
    model?: string | null;
    prompt_version?: string;
    automation_available: boolean;
    monetary_calculations_are_deterministic: boolean;
  };
};

export type OrderSummary = {
  id: number;
  status: string;
  total_bdt: string;
  advance_bdt: string;
  remaining_bdt: string;
  saved_quote_id?: number | null;
  country_id?: string;
  mode?: string;
  delivery_type?: string;
  shipping_bdt?: string;
  created_at?: string;
  updated_at?: string;
  manual_payment?: {
    channel: string;
    trx_id: string;
    verified: boolean;
    verified_at?: string | null;
    screenshot_url?: string | null;
    decision?: "PENDING" | "APPROVED" | "REJECTED" | "REVERSED" | string;
    decision_reason?: string | null;
    decided_at?: string | null;
    created_at?: string;
  } | null;
};

export type OrderItem = {
  variant_id: number;
  qty: number;
  product_name: string | null;
  variant_name: string | null;
};

export type OrderHistoryEntry = {
  status: string;
  created_at: string;
  note?: string | null;
};

export type OrderDetail = OrderSummary & {
  items?: OrderItem[];
  history?: OrderHistoryEntry[];
  shipment?: {
    tracking_number?: string | null;
    events?: Array<{
      status: string;
      note?: string | null;
      created_at: string;
    }>;
  };
  quote_snapshot?: QuoteResponse | null;
};

export type SavedQuote = {
  id: number;
  variant_id: number;
  product_name: string;
  variant_name: string;
  qty: number;
  country_id: string;
  mode: string;
  delivery_type: string;
  response: QuoteResponse & { sourcing_score?: string; risk_level?: string };
  status?: string;
  expires_at?: string | null;
  created_at?: string;
  updated_at?: string;
  order_ids?: number[];
};

export type RecommendationMethodology = {
  type: string;
  summary: string;
  weights: Record<string, string | null>;
};

export type RecommendationItem = {
  rank: number;
  country: Country;
  mode: string;
  score: string;
  estimated_total_bdt: string;
  estimated_shipping_bdt: string;
  estimated_duty_vat_bdt: string;
  estimated_service_fee_bdt: string;
  eta: {
    min_days: number;
    max_days: number;
  };
  quality_score: string;
  reliability_score: string;
  risk_level: "Low" | "Medium" | "High";
  risk_score: string;
  advantages: string[];
  weaknesses: string[];
  selected_offer: {
    id: number;
    seller_name: string;
    price_origin: string;
    currency: string;
    stock: number;
    moq: number;
    source_url: string | null;
  };
  reason: string;
};

export type CheapestCountryRecommendation = {
  product: {
    id: number;
    name: string;
    slug: string;
    variant_id: number;
    variant_name: string;
  };
  priority: string;
  delivery_type: string;
  qty: number;
  methodology: RecommendationMethodology;
  recommendations: RecommendationItem[];
  data_gaps: string[];
};

export type AiInsights = {
  methodology: string;
  supply_chain?: {
    matched_rows: number;
    top_product_type: string;
    top_supplier: string;
    top_route: string;
    average_defect_rate: string;
    summary: string;
  };
  sales?: {
    matched_rows: number;
    total_quantity_sold: number;
    average_unit_price: string;
    top_brand: string;
    top_region: string;
    top_product_type: string;
    summary: string;
  };
  market_signals?: Array<{
    name: string;
    period_change_percent: string;
    direction: string;
  }>;
  campaigns?: {
    campaign_count: number;
    top_channel: string;
    top_discount_type: string;
  };
  recommendations: string[];
};

const productionApiBase = process.env.VERCEL_ENV === "production"
  ? "https://cross-border-product-sourcing-api.onrender.com"
  : "";
// Browser traffic is always same-origin. This also prevents a stale Vercel
// NEXT_PUBLIC_API_BASE_URL value from sending cookies or catalog requests to an
// obsolete host.
const publicApiBase = "";
const serverApiBase = (
  productionApiBase
  || process.env.API_BASE_URL
  || (process.env.NODE_ENV === "development" ? "http://localhost:8001" : "")
).replace(/\/+$/, "");
let refreshRequest: Promise<boolean> | null = null;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryAfter: number | null;
  readonly requestId: string | null;

  constructor(
    message: string,
    {
      status = 0,
      code = "request_failed",
      retryAfter = null,
      requestId = null,
      cause,
    }: {
      status?: number;
      code?: string;
      retryAfter?: number | null;
      requestId?: string | null;
      cause?: unknown;
    } = {},
  ) {
    super(message, { cause });
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
    this.requestId = requestId;
  }
}

function responseErrorCode(status: number) {
  if (status === 401) return "invalid_credentials";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 423) return "account_locked";
  if (status === 429) return "rate_limited";
  if (status >= 500) return "service_unavailable";
  return "request_failed";
}

async function responseError(response: Response, fallback?: string): Promise<ApiError> {
  const payload = await response.json().catch(() => ({})) as {
    detail?: string | Array<{ msg?: string }>;
  };
  const detail = typeof payload.detail === "string"
    ? payload.detail
    : Array.isArray(payload.detail)
      ? payload.detail.map(item => item.msg).filter(Boolean).join("; ")
      : "";
  const retryAfterValue = Number(response.headers.get("retry-after"));
  return new ApiError(detail || fallback || `Request failed: ${response.status}`, {
    status: response.status,
    code: responseErrorCode(response.status),
    retryAfter: Number.isFinite(retryAfterValue) && retryAfterValue > 0
      ? retryAfterValue
      : null,
    requestId: response.headers.get("x-request-id"),
  });
}

export function isApiServiceUnavailable(error: unknown): boolean {
  return error instanceof ApiError
    ? error.status === 0 || error.status === 404 || error.status >= 500
    : error instanceof TypeError;
}

export type AuthServiceStatus = {
  available: boolean;
  status: "ready" | "unavailable";
  httpStatus: number | null;
  requestId: string | null;
};

function getRequestBase() {
  if (typeof window === "undefined") {
    if (!serverApiBase) {
      throw new Error("API_BASE_URL is required for server-side API requests");
    }
    return serverApiBase;
  }
  return publicApiBase;
}

export function resolveImageUrl(src: string | null | undefined) {
  const value = src?.trim();
  if (!value) return null;
  if (/^https?:\/\/(?:www\.)?loremflickr\.com\//i.test(value)) return null;
  if (/^https?:\/\//i.test(value)) return value;
  if (value.startsWith("//")) return `https:${value}`;
  if (value.startsWith("products/")) return `${publicApiBase}/media/${value}`;
  const normalized = value.startsWith("/") ? value : `/${value}`;
  return `${publicApiBase}${normalized}`;
}

function resolveMediaKind(
  value: string | null | undefined,
  hasImage: boolean,
): ProductMediaKind {
  const normalized = value?.trim().toLowerCase() || "";
  if (normalized.includes("supplier")) return "supplier";
  if (
    normalized.includes("illustrat")
    || normalized.includes("generated")
    || normalized.includes("fallback")
  ) {
    return "illustrative";
  }
  if (normalized.includes("reference") || normalized.includes("catalog")) {
    return "reference";
  }
  return hasImage ? "reference" : "illustrative";
}

export function getProductMedia(product: Product): ResolvedProductMedia[] {
  const suppliedMedia = Array.isArray(product.images)
    ? product.images
        .map((item, index) => ({ item, index }))
        .sort((a, b) => Number(Boolean(b.item.is_primary)) - Number(Boolean(a.item.is_primary)))
    : [];
  const candidates = [
    ...suppliedMedia.map(({ item, index }) => ({
        key: String(item.id ?? index),
        rawSrc: item.src ?? item.url ?? item.image,
        alt: item.alt,
        kind: item.kind ?? item.source,
        verified: item.verified,
      })),
    {
      key: "primary",
      rawSrc: product.image_metadata?.url ?? product.image,
      alt: product.image_metadata?.alt ?? product.image_alt,
      kind: product.image_metadata?.kind ?? product.image_source,
      verified: product.image_verified,
    },
  ];
  const seen = new Set<string>();
  const media = candidates.flatMap((candidate) => {
    const src = resolveImageUrl(candidate.rawSrc);
    if (!src || seen.has(src)) return [];
    seen.add(src);
    return [{
      key: `${candidate.key}-${src}`,
      src,
      alt: candidate.alt?.trim() || product.name,
      kind: resolveMediaKind(candidate.kind, true),
      verified: Boolean(candidate.verified),
    } satisfies ResolvedProductMedia];
  });

  return media.length
    ? media
    : [{
        key: "illustrative-fallback",
        src: null,
        alt: product.name,
        kind: "illustrative",
        verified: false,
      }];
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await apiFetch(path, {
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    } as Record<string, string>,
  });

  if (!response.ok) {
    throw await responseError(response);
  }

  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    throw await responseError(response);
  }

  return response.json() as Promise<T>;
}

async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json() as Promise<T>;
}

async function refreshSession(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (!refreshRequest) {
    refreshRequest = fetch(`${getRequestBase()}/api/auth/refresh/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      cache: "no-store",
    }).then((response) => response.ok).catch(() => false).finally(() => {
      refreshRequest = null;
    });
  }
  return refreshRequest;
}

async function apiFetch(path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${getRequestBase()}${path}`, init);
  } catch (cause) {
    throw new ApiError("Unable to reach the account service.", {
      code: "network_error",
      cause,
    });
  }
  const authEntryPoint = path === "/api/auth/login/" || path === "/api/auth/register/" || path === "/api/auth/refresh/";
  if (response.status === 401 && !authEntryPoint && await refreshSession()) {
    response = await fetch(`${getRequestBase()}${path}`, init);
  }
  return response;
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await apiFetch(path, {
    cache: "no-store",
    credentials: "include",
    ...init,
    headers,
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json() as Promise<T>;
}

export async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await apiFetch(path, {
    cache: "no-store",
    credentials: "include",
    ...init,
    headers,
  });
  if (!response.ok) {
    throw await responseError(response);
  }
}

export type CurrentUser = { id: number; username?: string; email?: string; phone?: string; role: string };
export type AuthSuccess = { user: CurrentUser; roles: string[] };
export type MfaRequired = {
  mfa_required: true;
  mfa_enrollment_required: boolean;
  mfa_token: string;
  expires_in: number;
};
export type LoginResult = AuthSuccess | MfaRequired;
export function loginWithCredentials(identifier: string, password: string, remember = true, portal: "customer" | "admin" = "customer") {
  return postJson<LoginResult>("/api/auth/login/", { identifier, password, remember, portal });
}
export function registerAccount(payload: { username: string; email?: string; phone?: string; password: string }) {
  return postJson<{ user: CurrentUser; message: string }>("/api/auth/register/", payload);
}
export function getCurrentUser() { return fetchJson<CurrentUser>("/api/auth/me/"); }
export async function getAuthServiceStatus(timeoutMs = 5000): Promise<AuthServiceStatus> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${getRequestBase()}/api/ready`, {
      cache: "no-store",
      credentials: "include",
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({})) as { status?: string };
    return {
      available: response.ok && payload.status === "ready",
      status: response.ok && payload.status === "ready" ? "ready" : "unavailable",
      httpStatus: response.status,
      requestId: response.headers.get("x-request-id"),
    };
  } catch {
    return {
      available: false,
      status: "unavailable",
      httpStatus: null,
      requestId: null,
    };
  } finally {
    window.clearTimeout(timeout);
  }
}
export function startMfaEnrollment(mfaToken: string) {
  return postJson<{ secret: string; otpauth_uri: string; message?: string }>("/api/auth/mfa/enroll/start/", { mfa_token: mfaToken });
}
export function confirmMfaEnrollment(mfaToken: string, code: string) {
  return postJson<AuthSuccess & { recovery_codes: string[]; message?: string }>("/api/auth/mfa/enroll/confirm/", { mfa_token: mfaToken, code });
}
export function verifyMfaLogin(mfaToken: string, input: { code?: string; recovery_code?: string }) {
  return postJson<AuthSuccess & { recovery_code_used?: boolean }>("/api/auth/mfa/verify/", { mfa_token: mfaToken, ...input });
}
export async function startGoogleLogin() {
  const response = await apiFetch("/api/auth/social/google/start/", { credentials: "include", cache: "no-store" });
  const data = await response.json().catch(() => ({})) as { auth_url?: string; detail?: string };
  if (!response.ok) {
    throw new ApiError(data.detail || "Google login is unavailable", {
      status: response.status,
      code: response.status >= 500 ? "social_login_unavailable" : responseErrorCode(response.status),
      requestId: response.headers.get("x-request-id"),
    });
  }
  if (!data.auth_url) throw new ApiError("Google login is unavailable", {
    status: response.status,
    code: "social_login_unavailable",
    requestId: response.headers.get("x-request-id"),
  });
  window.location.assign(data.auth_url);
}
export async function logoutSession() {
  await fetch(`${getRequestBase()}/api/auth/logout/`, { method: "POST", credentials: "include" });
}

const catalogSnapshotFallbackEnabled =
  process.env.NEXT_PUBLIC_CATALOG_SNAPSHOT_FALLBACK !== "0";

export async function getProducts(query?: string) {
  const path = query ? `/api/products/?q=${encodeURIComponent(query)}` : "/api/products/";
  let liveProducts: Product[] | null = null;
  let liveError: unknown;
  try {
    liveProducts = await fetchJson<Product[]>(path);
  } catch (error) {
    liveError = error;
  }
  if (!catalogSnapshotFallbackEnabled) {
    if (liveProducts) return liveProducts;
    throw liveError;
  }
  const { getSnapshotProducts } = await import("./public-catalog");
  const snapshotProducts = getSnapshotProducts(query);
  return liveProducts && liveProducts.length >= snapshotProducts.length
    ? liveProducts
    : snapshotProducts;
}

export type ProductPage = { items: Product[]; total: number; page: number; page_size: number; pages: number; catalog_source?: "snapshot" };
export async function browseProducts(input: { q?: string; category?: string; page?: number; pageSize?: number; sort?: string; country?: string; maxPrice?: number; maxDelivery?: number; minRating?: number; risk?: string }) {
  const params = new URLSearchParams({ q: input.q || "", category: input.category || "", page: String(input.page || 1), page_size: String(input.pageSize || 24), sort: input.sort || "name", country: input.country || "", risk: input.risk || "" });
  if (input.maxPrice !== undefined) params.set("max_price", String(input.maxPrice)); if (input.maxDelivery !== undefined) params.set("max_delivery", String(input.maxDelivery)); if (input.minRating !== undefined) params.set("min_rating", String(input.minRating));
  let livePage: ProductPage | null = null;
  let liveError: unknown;
  try {
    livePage = await fetchJson<ProductPage>(`/api/catalog/browse/?${params.toString()}`);
  } catch (error) {
    liveError = error;
  }
  if (!catalogSnapshotFallbackEnabled) {
    if (livePage) return livePage;
    throw liveError;
  }
  const { browseSnapshotProducts } = await import("./public-catalog");
  const snapshotPage = browseSnapshotProducts(input);
  return livePage && livePage.total >= snapshotPage.total ? livePage : snapshotPage;
}

export function getLiveCategories() {
  return fetchJson<Category[]>("/api/categories/");
}

export async function getCategories() {
  let liveCategories: Category[] | null = null;
  let liveError: unknown;
  try {
    liveCategories = await getLiveCategories();
  } catch (error) {
    liveError = error;
  }
  if (!catalogSnapshotFallbackEnabled) {
    if (liveCategories) return liveCategories;
    throw liveError;
  }
  const { getSnapshotCategories } = await import("./public-catalog");
  const snapshotCategories = getSnapshotCategories();
  return liveCategories && liveCategories.length >= snapshotCategories.length
    ? liveCategories
    : snapshotCategories;
}

export function getLiveCountries() {
  return fetchJson<Country[]>("/api/countries/");
}

export async function getCountries() {
  let liveCountries: Country[] | null = null;
  let liveError: unknown;
  try {
    liveCountries = await getLiveCountries();
  } catch (error) {
    liveError = error;
  }
  if (!catalogSnapshotFallbackEnabled) {
    if (liveCountries) return liveCountries;
    throw liveError;
  }
  const { getSnapshotCountries } = await import("./public-catalog");
  const snapshotCountries = getSnapshotCountries();
  return liveCountries && liveCountries.length >= snapshotCountries.length
    ? liveCountries
    : snapshotCountries;
}

export function getAiInsights(q = "") {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return fetchJson<AiInsights>(`/api/ai/insights/${query}`);
}

export async function getProductBySlug(slug: string) {
  try {
    return await fetchJson<Product>(`/api/products/${slug}/`);
  } catch (error) {
    if (!catalogSnapshotFallbackEnabled) throw error;
    const { getSnapshotProductBySlug } = await import("./public-catalog");
    return getSnapshotProductBySlug(slug);
  }
}

export function quoteProduct(payload: {
  variant_id: number;
  country: string;
  mode: string;
  qty: number;
  delivery_type: string;
}) {
  return postJson<QuoteResponse>("/api/quote/", payload);
}

export function quoteProductWithAi(payload: {
  variant_id: number;
  country: string;
  mode: string;
  qty: number;
  delivery_type: string;
}) {
  return postJson<QuoteResponse>("/api/quote/ai-explanation/", payload);
}

export function getCheapestCountryRecommendation(input: {
  variant_id?: number;
  product_slug?: string;
  qty?: number;
  delivery_type?: string;
  priority?: string;
  countries?: string[];
  weights?: Record<string, number>;
}) {
  return postJson<CheapestCountryRecommendation>("/api/recommendations/cheapest-country/", {
    qty: 1,
    delivery_type: "DOOR",
    priority: "balanced",
    ...input,
  });
}

export function saveQuote(payload: { variant_id: number; country: string; mode: string; qty: number; delivery_type: string; response: unknown; }) {
  return postJson<{ id: number }>("/api/quote/save/", payload);
}

export function getSavedQuotes() {
  return fetchJson<SavedQuote[]>("/api/quote/saved/");
}
export function getSavedQuote(id: string | number) {
  return fetchJson<SavedQuote>(`/api/quote/saved/${id}/`);
}
export async function deleteSavedQuote(id: number) { const response = await fetch(`${getRequestBase()}/api/quote/saved/${id}/`, { method: "DELETE", credentials: "include" }); if (!response.ok) throw new Error("Delete failed"); }
export function updateSavedQuoteStatus(id: number, status: "approved" | "requested") { return fetch(`${getRequestBase()}/api/quote/saved/${id}/status/`, { method: "PATCH", credentials: "include", headers: {"Content-Type":"application/json"}, body: JSON.stringify({status}) }).then(response => { if(!response.ok) throw new Error("Update failed"); return response.json(); }); }
export function getQuotePdfUrl(id: number) { return `${publicApiBase}/api/quote/saved/${id}/pdf/`; }

export type ResearchAnalytics = {
  cards: Record<string, number | string>;
  top_sourcing_countries: Array<{ country: string; quotes: number }>;
  evaluation: Record<string, Record<string, number | string | null>>;
};

export function getResearchAnalytics() {
  return fetchJson<ResearchAnalytics>("/api/research/analytics/");
}

export function getResearchExportUrl() {
  return `${publicApiBase}/api/research/export.csv`;
}
export type AdminOverview = {
  cards: Record<string, number | string>;
  supplier_alerts: Array<{ id: number; name: string; country: string; rating: number; risk: string }>;
  recent_orders: Array<{ id: number; user_id: number; status: string; country: string; mode: string; total_bdt: string; payment_verified: boolean }>;
  payment_queue: Array<{ order_id: number; channel: string; trx_id: string; advance_bdt: string }>;
  daily_revenue: Array<{ date: string; orders: number; order_value_bdt: string; shipping_bdt: string; verified_advance_bdt: string }>;
  top_items: Array<{ name: string; units: number }>;
  order_stages: Array<{ status: string; count: number; percentage: number }>;
  order_types: Array<{ type: string; count: number; percentage: number }>;
  delivery_options: Array<{ type: string; orders: number; orders_percentage: number; units: number; units_percentage: number }>;
  top_countries: Array<{ country: string; orders: number }>;
  comparison?: Record<string, { current: number | string; previous: number | string; change: number | string; change_percent: number | null }>;
  funnel?: Array<{ stage: string; count: number; percentage?: number; conversion_percent?: number | null }>;
  delivery_metrics?: {
    average_delivery_days?: number | string | null;
    delayed_shipments?: number | null;
    delivered_orders?: number | null;
    on_time_rate_percent?: number | string | null;
  };
  supplier_performance?: Array<{
    id?: number;
    name: string;
    orders?: number;
    defect_rate_percent?: number | string | null;
    reliability_percent?: number | string | null;
    fulfilment_sla_percent?: number | string | null;
  }>;
  profitability?: {
    countries?: Array<AdminProfitabilityRow>;
    categories?: Array<AdminProfitabilityRow>;
    products?: Array<AdminProfitabilityRow>;
  };
  freshness?: string;
  range?: { date_from: string; date_to: string; timezone: string; generated_at: string };
  payment_queue_total?: number;
};
export type AdminProfitabilityRow = {
  id?: number | string;
  name?: string;
  country?: string;
  category?: string;
  product?: string;
  revenue_bdt?: string | number | null;
  cost_bdt?: string | number | null;
  profit_bdt?: string | number | null;
  margin_percent?: string | number | null;
  orders?: number | null;
};

function dhakaDateRange(days: 1 | 7 | 30 | 90) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Dhaka",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value || "";
  const dateTo = `${value("year")}-${value("month")}-${value("day")}`;
  const start = new Date(`${dateTo}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - (days - 1));
  return { date_from: start.toISOString().slice(0, 10), date_to: dateTo };
}
export type AdminOverviewQuery = {
  date_from?: string;
  date_to?: string;
  timezone?: string;
  status?: string;
  country?: string;
  mode?: string;
  compare?: boolean;
};

export function getAdminOverview(input: 1 | 7 | 30 | 90 | AdminOverviewQuery = 30){
  const query: AdminOverviewQuery = typeof input === "number" ? dhakaDateRange(input) : input;
  return fetchJson<AdminOverview>(`/api/admin/overview/${toQuery({ ...query, timezone: query.timezone || "Asia/Dhaka", compare: String(query.compare ?? true) })}`);
}
export function updateOrderStatus(orderId: number, status: string, note?: string, trackingNumber?: string, shipmentNote?: string) {
  return postJson<{ id: number; status: string }>(`/api/orders/${orderId}/status/`, {
    status,
    note,
    tracking_number: trackingNumber || undefined,
    shipment_note: shipmentNote || undefined,
  });
}
export function verifyOrderPayment(orderId: number) {
  return postJson<{ id: number; status: string; payment_verified: boolean }>(`/api/admin/orders/${orderId}/verify-payment/`, {});
}

export type AdminListResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type AdminOrderRow = {
  id: number;
  user_id: number;
  customer?: string | { id?: number; username?: string | null; email?: string | null; phone?: string | null };
  customer_name?: string;
  status: string;
  country?: string;
  country_code?: string;
  mode?: string;
  delivery_type?: string;
  total_bdt: string | number;
  advance_bdt?: string | number;
  remaining_bdt?: string | number;
  payment_status?: string;
  payment_verified?: boolean;
  payment?: { id?: number; channel?: string; trx_id?: string; screenshot_url?: string | null; verified?: boolean; decision?: string; decision_reason?: string | null } | null;
  tracking_number?: string | null;
  created_at?: string;
};

export type AdminPaymentRow = {
  id?: number;
  order_id: number;
  user_id?: number;
  customer?: string | { id?: number; username?: string | null; email?: string | null; phone?: string | null };
  channel: string;
  trx_id: string;
  advance_bdt: string | number;
  status?: string;
  decision?: string;
  verified?: boolean;
  screenshot_url?: string | null;
  rejection_reason?: string | null;
  created_at?: string;
  submitted_at?: string;
  verified_at?: string | null;
  decided_at?: string | null;
};

export type AdminQuoteRow = {
  id: number;
  user_id?: number;
  customer?: string | { id?: number; username?: string | null; email?: string | null; phone?: string | null };
  product_name: string;
  variant_name?: string;
  qty: number;
  country?: string;
  country_code?: string;
  mode?: string;
  status?: string;
  total_bdt?: string | number;
  expires_at?: string | null;
  created_at?: string;
};

export type AdminProductRow = {
  id: number;
  name: string;
  slug?: string;
  model?: string | null;
  category?: string | { id?: number; name: string; slug?: string };
  variants?: number | unknown[];
  variant_count?: number;
  offers?: number;
  offer_count?: number;
  supplier_count?: number;
  status?: string;
  is_active?: boolean;
  description?: string | null;
  image?: string | null;
  archived_at?: string | null;
  updated_at?: string | null;
};

export type AdminSupplierRow = {
  id: number;
  name: string;
  country?: string | { id?: number; code?: string; name: string };
  rating?: string | number;
  risk?: string;
  offers?: number;
  offer_count?: number;
  products?: number;
  updated_at?: string | null;
  note?: string | null;
  is_active?: boolean;
  archived_at?: string | null;
};

export type AdminUserRow = {
  id: number;
  username?: string;
  email?: string | null;
  phone?: string | null;
  role: string;
  is_active?: boolean;
  is_staff?: boolean;
  orders?: number;
  saved_quotes?: number;
  created_at?: string;
};

export type AdminAuditRow = {
  id: number | string;
  actor?: string;
  actor_id?: number | null;
  actor_user_id?: number | null;
  actor_role?: string | null;
  action: string;
  entity?: string;
  entity_type?: string;
  entity_id?: number | string | null;
  detail?: string | null;
  note?: string | null;
  request_id?: string | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  ip_address?: string | null;
  created_at?: string;
};

function toQuery(params: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export function getAdminList<T>(
  resource: "orders" | "payments" | "quotes" | "products" | "categories" | "variants" | "suppliers" | "offers" | "users" | "audit",
  params: { q?: string; page?: number; page_size?: number; status?: string; decision?: string; country?: string; category?: string; risk?: string; role?: string; action?: string; date_from?: string; date_to?: string } = {},
) {
  const endpoint = resource === "audit" ? "audit-events" : resource;
  let query = toQuery({ page: 1, page_size: 20, ...params });
  if (resource === "payments" && !params.decision) query += `${query ? "&" : "?"}decision=`;
  return fetchJson<AdminListResponse<T>>(`/api/admin/${endpoint}/${query}`);
}

export function decideOrderPayment(orderId: number, decision: "approve" | "reject", reason?: string) {
  return patchJson<{ id: number; order_id?: number; status: string; payment_verified?: boolean }>(
    `/api/admin/orders/${orderId}/payment-decision/`,
    { decision: decision === "approve" ? "APPROVED" : "REJECTED", reason: reason || undefined, note: reason || undefined },
  );
}

export function createOrder(payload: {
  variant_id: number;
  country: string;
  mode: string;
  qty: number;
  delivery_type: string;
  offer_id?: number;
  saved_quote_id: number;
  idempotency_key: string;
  trx_id: string;
  channel: string;
  screenshot_url?: string;
}) {
  return apiFetch("/api/orders/create-manual/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": payload.idempotency_key,
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    credentials: "include",
  }).then(async response => {
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    return response.json() as Promise<{ order_id: number; status: string; saved_quote_id?: number; idempotent_replay?: boolean }>;
  });
}

export function getMyOrders() {
  return fetchJson<OrderSummary[]>("/api/orders/me/");
}

export function getOrderById(orderId: string | number) {
  return fetchJson<OrderDetail>(`/api/orders/${orderId}/`);
}
