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

export type Product = {
  id: number;
  name: string;
  slug: string;
  model: string | null;
  description: string | null;
  image: string | null;
  category: Category;
  variants: ProductVariant[];
  default_variant_id: number | null;
  market?: { min_price?: number; currency?: string; max_rating?: number; min_delivery_days?: number; risk_level?: string; supplier_count?: number; countries?: string[]; recommended_score?: number };
};

export type Country = {
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
};

export type OrderSummary = {
  id: number;
  status: string;
  total_bdt: string;
  advance_bdt: string;
  remaining_bdt: string;
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
  manual_payment?: {
    channel: string;
    trx_id: string;
    verified: boolean;
    verified_at?: string | null;
    screenshot_url?: string | null;
  };
};

export type SavedQuote = {
  id: number;
  product_name: string;
  variant_name: string;
  qty: number;
  country_id: string;
  mode: string;
  response: QuoteResponse & { sourcing_score?: string; risk_level?: string };
  status?: string;
  expires_at?: string | null;
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

const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8001";
const serverApiBase = process.env.API_BASE_URL || publicApiBase;

function getRequestBase() {
  if (typeof window === "undefined") {
    return process.env.NODE_ENV === "development" ? publicApiBase : serverApiBase;
  }
  return publicApiBase;
}

export function resolveImageUrl(src: string | null | undefined) {
  if (!src) return null;
  if (/^https?:\/\//i.test(src) || src.startsWith("//")) return src;
  const normalized = src.startsWith("/") ? src : `/${src}`;
  return `${publicApiBase}${normalized}`;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${getRequestBase()}${path}`, {
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    } as Record<string, string>,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${getRequestBase()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export type CurrentUser = { id: number; username?: string; email?: string; phone?: string; role: string };
export function loginWithCredentials(identifier: string, password: string) {
  return postJson<{ user: CurrentUser; roles: string[] }>("/api/auth/login/", { identifier, password });
}
export function getCurrentUser() { return fetchJson<CurrentUser>("/api/auth/me/"); }
export async function logoutSession() {
  await fetch(`${getRequestBase()}/api/auth/logout/`, { method: "POST", credentials: "include" });
}

export function getProducts(query?: string) {
  const path = query ? `/api/products/?q=${encodeURIComponent(query)}` : "/api/products/";
  return fetchJson<Product[]>(path);
}

export type ProductPage = { items: Product[]; total: number; page: number; page_size: number; pages: number };
export function browseProducts(input: { q?: string; category?: string; page?: number; pageSize?: number; sort?: string; country?: string; maxPrice?: number; maxDelivery?: number; minRating?: number; risk?: string }) {
  const params = new URLSearchParams({ q: input.q || "", category: input.category || "", page: String(input.page || 1), page_size: String(input.pageSize || 24), sort: input.sort || "name", country: input.country || "", risk: input.risk || "" });
  if (input.maxPrice !== undefined) params.set("max_price", String(input.maxPrice)); if (input.maxDelivery !== undefined) params.set("max_delivery", String(input.maxDelivery)); if (input.minRating !== undefined) params.set("min_rating", String(input.minRating));
  return fetchJson<ProductPage>(`/api/catalog/browse/?${params.toString()}`);
}

export function getCategories() {
  return fetchJson<Category[]>("/api/categories/");
}

export function getCountries() {
  return fetchJson<Country[]>("/api/countries/");
}

export function getAiInsights(q = "") {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return fetchJson<AiInsights>(`/api/ai/insights/${query}`);
}

export function getProductBySlug(slug: string) {
  return fetchJson<Product>(`/api/products/${slug}/`);
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
export type AdminOverview = { cards: Record<string,number>; supplier_alerts: Array<{id:number;name:string;country:string;rating:number;risk:string}> };
export function getAdminOverview(){return fetchJson<AdminOverview>("/api/admin/overview/");}

export function createOrder(payload: {
  variant_id: number;
  country: string;
  mode: string;
  qty: number;
  delivery_type: string;
  offer_id?: number;
  trx_id: string;
  channel: string;
  screenshot_url?: string;
}) {
  return postJson<{ order_id: number; status: string }>("/api/orders/create-manual/", payload);
}

export function getMyOrders() {
  return fetchJson<OrderSummary[]>("/api/orders/me/");
}

export function getOrderById(orderId: string | number) {
  return fetchJson<OrderDetail>(`/api/orders/${orderId}/`);
}
