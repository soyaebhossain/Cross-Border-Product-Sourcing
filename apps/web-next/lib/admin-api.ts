import { requestJson, requestVoid, type AdminListResponse, type AdminUserRow, type QuoteResponse } from "./api";

export type ArchivedEntity = {
  id: number;
  is_active: boolean;
  archived_at?: string | null;
  archived_by_user_id?: number | null;
};

export type AdminCategory = ArchivedEntity & {
  name: string;
  slug: string;
  product_count: number;
};

export type AdminVariant = ArchivedEntity & {
  product_id: number;
  product_name?: string | null;
  sku?: string | null;
  variant_name?: string | null;
  weight_kg: string;
  length_cm: string;
  width_cm: string;
  height_cm: string;
  offer_count: number;
};

export type AdminProduct = ArchivedEntity & {
  name: string;
  slug: string;
  model?: string | null;
  description?: string | null;
  image?: string | null;
  category: AdminCategory;
  variants: AdminVariant[];
};

export type AdminSupplier = ArchivedEntity & {
  name: string;
  country: { id: number; code: string; name: string };
  rating: number;
  note?: string | null;
  offer_count: number;
};

export type AdminOffer = ArchivedEntity & {
  variant: { id: number; sku?: string | null; name?: string | null; product_id: number; product_name: string };
  supplier: { id: number; name: string };
  country: { id: number; code: string; name: string };
  mode: "LOCAL" | "BULK";
  price_origin: string;
  currency: string;
  stock: number;
  moq: number;
  source_url?: string | null;
  updated_at?: string | null;
};

export type AdminAdjustment = {
  id: number;
  order_id: number;
  type?: string;
  adjustment_type?: string;
  status?: string;
  amount_bdt: string;
  transaction_id?: string | null;
  reason?: string | null;
  note?: string | null;
  created_at?: string;
  reversed_at?: string | null;
};

export type AdminOrderDetail = {
  id: number;
  customer: AdminUserRow;
  saved_quote_id?: number | null;
  status: string;
  country: string;
  mode: string;
  delivery_type: string;
  total_bdt: string;
  shipping_bdt: string;
  advance_bdt: string;
  remaining_bdt: string;
  actual_cost_bdt?: string | null;
  promised_delivery_at?: string | null;
  delivered_at?: string | null;
  quality_defect_reported?: boolean | null;
  quote_snapshot?: QuoteResponse | null;
  items: Array<{ id: number; variant_id: number; offer_id?: number | null; product_name?: string | null; variant_name?: string | null; qty: number }>;
  payment?: {
    id: number;
    channel: string;
    transaction_id: string;
    proof_url?: string | null;
    decision: string;
    reason?: string | null;
    verified: boolean;
    verified_at?: string | null;
    decided_at?: string | null;
    verifier?: AdminUserRow | null;
    submitted_at?: string | null;
  } | null;
  financials?: Record<string, string | number | null>;
  adjustments?: AdminAdjustment[];
  history?: Array<{ id: number; status: string; note?: string | null; actor_user_id?: number | null; actor_role?: string | null; request_id?: string | null; created_at: string }>;
  shipment?: { tracking_number?: string | null; events?: Array<{ id: number; status: string; note?: string | null; created_at: string }> } | null;
  created_at?: string;
  updated_at?: string;
};

export type AdminQuoteDetail = {
  id: number;
  customer: AdminUserRow;
  variant_id: number;
  product_name: string;
  variant_name?: string | null;
  country: string;
  mode: string;
  delivery_type: string;
  qty: number;
  status: string;
  expires_at?: string | null;
  snapshot?: QuoteResponse | null;
  order_ids: number[];
  created_at?: string;
  updated_at?: string;
  ai_review?: AdminAIReview | null;
};

export type AdminAIReview = {
  id: number;
  saved_quote_id: number;
  product_name: string;
  variant_name?: string | null;
  country: string;
  mode: string;
  qty: number;
  provider: string;
  model?: string | null;
  prompt_version: string;
  explanation: NonNullable<QuoteResponse["ai_explanation"]>;
  confidence?: string | number | null;
  human_review_required: boolean;
  review_status: "PENDING" | "APPROVED" | "REJECTED" | "NOT_REQUIRED" | string;
  review_note?: string | null;
  reviewed_by_user_id?: number | null;
  reviewed_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type AdminSettings = {
  currencies: Array<{ id: number; currency: string; rate_to_bdt: string; is_active: boolean; updated_at?: string }>;
  service_fees: Array<{ id: number; mode: "LOCAL" | "BULK"; fee_bdt: string; percent: string; is_active: boolean; updated_at?: string }>;
  shipping_rates: Array<{ id: number; country_id: number; country: string; method: "AIR" | "SEA"; min_kg: string; max_kg: string; cost_bdt: string; is_active: boolean; updated_at?: string }>;
  eta_rules: Array<{ id: number; country_id: number; country: string; mode: "LOCAL" | "BULK"; delivery_type: "DOOR" | "PICKUP"; min_days: number; max_days: number; is_active: boolean; updated_at?: string }>;
  duty_rules: Array<{ id: number; country_id: number; country: string; category_id?: number | null; category?: string | null; percent: string; fixed_bdt: string; effective_from?: string | null; effective_to?: string | null; is_active: boolean; updated_at?: string }>;
};

export type AnalyticsOverview = {
  range: { date_from: string; date_to: string; timezone: string; comparison_date_from?: string | null; comparison_date_to?: string | null; filters?: Record<string, string | null> };
  generated_at: string;
  data_last_updated_at?: string | null;
  metric_version: string;
  metric_definitions: Record<string, string>;
  cards: Record<string, string | number | null>;
  daily_financials?: Array<{ date: string; orders: number; gross_order_value_bdt: string; verified_cash_bdt: string; refunds_bdt: string }>;
  comparison?: Record<string, { current: string | number; previous: string | number; change: string | number; change_percent: number | null }> | null;
  funnel: {
    saved_quotes: number;
    ordered_quotes: number;
    delivered_quotes: number;
    quote_to_order_conversion_pct: number | null;
    order_to_delivered_conversion_pct: number | null;
    quote_to_delivered_conversion_pct: number | null;
  };
  delivery: {
    average_delivery_days: number | null;
    delivered_with_timestamp: number;
    delivered_late: number;
    active_overdue: number;
    delayed_shipments: number;
  };
  supplier_performance: SupplierAnalyticsRow[];
  profitability_by_country: ProfitabilityRow[];
  coverage: { orders_with_actual_cost: number; delivered_with_timestamp: number; supplier_rows_with_outcomes: number };
  cache?: { hit: boolean; ttl_seconds: number };
};

export type SupplierAnalyticsRow = {
  supplier_id: number;
  supplier_name: string;
  catalog_rating: number;
  orders: number;
  delivered_orders: number;
  defect_orders: number;
  defect_rate_pct: number | null;
  sla_eligible_orders: number;
  on_time_orders: number;
  sla_pct: number | null;
  reliability_pct: number | null;
};

export type ProfitabilityRow = {
  key: number | string;
  name: string;
  orders: number;
  revenue_bdt: string;
  actual_cost_bdt: string;
  margin_bdt: string;
  margin_pct: number | null;
};

export type DelayedOrderRow = {
  order_id: number;
  status: string;
  country: string;
  promised_delivery_at?: string | null;
  delivered_at?: string | null;
  delay_type: "delivered_late" | "active_overdue";
};

export type AdminRoleContract = {
  items: Array<{ role: "customer" | "operator" | "admin"; capabilities: string[]; users: number; system_managed: boolean }>;
  policy: string;
};

function queryString(params: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

function json(method: string, body: unknown): RequestInit {
  return { method, body: JSON.stringify(body) };
}

export function listAdminCategories(params: { q?: string; page?: number; page_size?: number; active?: boolean } = {}) {
  return requestJson<AdminListResponse<AdminCategory>>(`/api/admin/categories/${queryString(params)}`);
}
export function getAdminCategory(id: number | string) { return requestJson<AdminCategory>(`/api/admin/categories/${id}/`); }
export function createAdminCategory(payload: { name: string; slug: string }) { return requestJson<AdminCategory>("/api/admin/categories/", json("POST", payload)); }
export function updateAdminCategory(id: number, payload: { name?: string; slug?: string; note: string }) { return requestJson<AdminCategory>(`/api/admin/categories/${id}/`, json("PATCH", payload)); }

export function getAdminProduct(id: number | string) { return requestJson<AdminProduct>(`/api/admin/products/${id}/`); }
export function createAdminProduct(payload: { name: string; slug: string; category_id: number; model?: string; description?: string; image?: string }) { return requestJson<AdminProduct>("/api/admin/products/", json("POST", payload)); }
export function updateAdminProduct(id: number, payload: Partial<{ name: string; slug: string; category_id: number; model: string | null; description: string | null; image: string | null }> & { note: string }) { return requestJson<AdminProduct>(`/api/admin/products/${id}/`, json("PATCH", payload)); }

export function listAdminVariants(params: { q?: string; product_id?: number; active?: boolean; page?: number; page_size?: number } = {}) { return requestJson<AdminListResponse<AdminVariant>>(`/api/admin/variants/${queryString(params)}`); }
export function getAdminVariant(id: number | string) { return requestJson<AdminVariant>(`/api/admin/variants/${id}/`); }
export function createAdminVariant(payload: { product_id: number; sku?: string; variant_name?: string; weight_kg: number; length_cm: number; width_cm: number; height_cm: number }) { return requestJson<AdminVariant>("/api/admin/variants/", json("POST", payload)); }
export function updateAdminVariant(id: number, payload: Partial<{ sku: string | null; variant_name: string | null; weight_kg: number; length_cm: number; width_cm: number; height_cm: number }> & { note: string }) { return requestJson<AdminVariant>(`/api/admin/variants/${id}/`, json("PATCH", payload)); }

export function getAdminSupplier(id: number | string) { return requestJson<AdminSupplier>(`/api/admin/suppliers/${id}/`); }
export function createAdminSupplier(payload: { country_id: number; name: string; rating: number; note?: string }) { return requestJson<AdminSupplier>("/api/admin/suppliers/", json("POST", payload)); }
export function updateAdminSupplier(id: number, payload: Partial<{ country_id: number; name: string; rating: number; supplier_note: string | null }> & { note: string }) { return requestJson<AdminSupplier>(`/api/admin/suppliers/${id}/`, json("PATCH", payload)); }

export function listAdminOffers(params: { q?: string; supplier_id?: number; variant_id?: number; country?: string; mode?: string; active?: boolean; page?: number; page_size?: number } = {}) { return requestJson<AdminListResponse<AdminOffer>>(`/api/admin/offers/${queryString(params)}`); }
export function getAdminOffer(id: number | string) { return requestJson<AdminOffer>(`/api/admin/offers/${id}/`); }
export function createAdminOffer(payload: { variant_id: number; country_id: number; seller_id: number; mode: "LOCAL" | "BULK"; price_origin: number; currency: string; stock: number; moq: number; source_url?: string }) { return requestJson<AdminOffer>("/api/admin/offers/", json("POST", payload)); }
export function updateAdminOffer(id: number, payload: Partial<{ variant_id: number; country_id: number; seller_id: number; mode: "LOCAL" | "BULK"; price_origin: number; currency: string; stock: number; moq: number; source_url: string | null }> & { note: string }) { return requestJson<AdminOffer>(`/api/admin/offers/${id}/`, json("PATCH", payload)); }

export function archiveAdminEntity(entity: "categories" | "products" | "variants" | "suppliers" | "offers", id: number, archived: boolean, note: string) {
  return requestVoid(`/api/admin/${entity}/${id}/`, json("DELETE", { archived, note }));
}
export function bulkArchiveAdminEntities(entity: "categories" | "products" | "variants" | "suppliers" | "offers", ids: number[], archived: boolean, note: string) {
  return requestJson<{ entity_type: string; ids: number[]; archived: boolean }>(`/api/admin/catalog/${entity}/bulk-archive/`, json("POST", { ids, archived, note }));
}

export function getAdminUser(id: number | string) { return requestJson<AdminUserRow>(`/api/admin/users/${id}/`); }
export function updateAdminUser(id: number, payload: { role?: "customer" | "operator" | "admin"; is_active?: boolean; note: string }) { return requestJson<AdminUserRow>(`/api/admin/users/${id}/`, json("PATCH", payload)); }
export function getAdminRoles() { return requestJson<AdminRoleContract>("/api/admin/roles/"); }
export function getAdminOrderDetail(id: number | string) { return requestJson<AdminOrderDetail>(`/api/admin/orders/${id}/`); }
export function getAdminPaymentDetail(id: number | string) { return requestJson<{ payment: NonNullable<AdminOrderDetail["payment"]>; order: AdminOrderDetail }>(`/api/admin/payments/${id}/`); }
export function getAdminQuoteDetail(id: number | string) { return requestJson<AdminQuoteDetail>(`/api/admin/quotes/${id}/`); }
export function decideAdminAIReview(id: number, decision: "APPROVED" | "REJECTED", note: string) { return requestJson<AdminAIReview>(`/api/admin/ai-reviews/${id}/`, json("PATCH", { decision, note })); }
export function getAdminAIReviews(status = "PENDING", page = 1) { return requestJson<AdminListResponse<AdminAIReview>>(`/api/admin/ai-reviews/${queryString({ status, page, page_size: 50 })}`); }
export function updateAdminSettlement(id: number, payload: Partial<{ actual_cost_bdt: number; promised_delivery_at: string; delivered_at: string; quality_defect_reported: boolean }> & { note: string }) { return requestJson<AdminOrderDetail>(`/api/admin/orders/${id}/settlement/`, json("PATCH", payload)); }
export function reverseAdminPayment(id: number, note: string) { return requestJson<{ order: AdminOrderDetail; reversal: AdminAdjustment }>(`/api/admin/payments/${id}/reverse/`, json("POST", { note })); }
export function createAdminRefund(orderId: number, payload: { amount_bdt: number; transaction_id?: string; reason: string }) { return requestJson<{ refund: AdminAdjustment; financials: Record<string, string | number | null> }>(`/api/admin/orders/${orderId}/refunds/`, json("POST", payload)); }
export function reverseAdminRefund(id: number, note: string) { return requestJson<{ refund: AdminAdjustment; financials: Record<string, string | number | null> }>(`/api/admin/refunds/${id}/reverse/`, json("POST", { note })); }

export function getAdminSettings() { return requestJson<AdminSettings>("/api/admin/settings/"); }
export function saveAdminSetting<T extends Record<string, unknown>>(type: "currencies" | "service-fees" | "shipping-rates" | "eta-rules" | "duty-rules", payload: T, id?: number) {
  const path = id ? `/api/admin/settings/${type}/${id}/` : `/api/admin/settings/${type}/`;
  return requestJson<Record<string, unknown>>(path, json(id ? "PUT" : "POST", payload));
}
export function archiveAdminSetting(type: "currencies" | "service-fees" | "shipping-rates" | "eta-rules" | "duty-rules", id: number, archived: boolean, note: string) {
  return requestVoid(`/api/admin/settings/${type}/${id}/`, json("DELETE", { archived, note }));
}

export type AnalyticsQuery = { date_from?: string; date_to?: string; days?: number; timezone?: string; country?: string; mode?: string; status?: string; page?: number; page_size?: number };
export function getAnalyticsOverview(params: AnalyticsQuery) { return requestJson<AnalyticsOverview>(`/api/admin/analytics/overview/${queryString({ ...params, compare: true })}`); }
export function getSupplierAnalytics(params: AnalyticsQuery) { return requestJson<AdminListResponse<SupplierAnalyticsRow> & { metric_definitions: Record<string, string> }>(`/api/admin/analytics/suppliers/${queryString(params)}`); }
export function getProfitabilityAnalytics(params: AnalyticsQuery & { dimension: "country" | "category" | "product" }) { return requestJson<AdminListResponse<ProfitabilityRow> & { dimension: string; metric_definition: string; empty_state?: string | null }>(`/api/admin/analytics/profitability/${queryString(params)}`); }
export function getDelayAnalytics(params: AnalyticsQuery) { return requestJson<AdminListResponse<DelayedOrderRow>>(`/api/admin/analytics/delays/${queryString(params)}`); }
