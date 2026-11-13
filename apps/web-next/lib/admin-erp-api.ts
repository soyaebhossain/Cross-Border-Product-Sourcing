import { requestJson, type AdminListResponse } from "./api";

export type PurchaseOrderStatus = "DRAFT" | "SENT" | "CONFIRMED" | "RECEIVED" | "CLOSED" | "CANCELLED";

export type PurchaseOrder = {
  id: number;
  po_number: string;
  order_id: number;
  order_status?: string | null;
  supplier: { id: number; name: string };
  status: PurchaseOrderStatus;
  currency: string;
  fx_rate_to_bdt: string;
  total_origin: string;
  total_bdt: string;
  paid_origin: string;
  paid_bdt: string;
  outstanding_origin: string;
  outstanding_bdt: string;
  ordered_qty: number;
  received_qty: number;
  rejected_qty: number;
  expected_at?: string | null;
  note?: string | null;
  created_at?: string;
  updated_at?: string;
  allowed_statuses: PurchaseOrderStatus[];
  items?: Array<{ id: number; variant_id: number; product_name: string; variant_name: string; qty: number; unit_cost_origin: string; line_total_origin: string }>;
  receipts?: Array<{ id: number; received_qty: number; accepted_qty: number; rejected_qty: number; qc_note?: string | null; received_at?: string }>;
  payments?: Array<{ id: number; amount_origin: string; currency: string; fx_rate_to_bdt: string; amount_bdt: string; method: string; reference?: string | null; paid_at?: string; status: "POSTED" | "REVERSED"; reversal_reason?: string | null }>;
};

export type PayablesReport = {
  generated_at: string;
  items: Array<PurchaseOrder & { age_days: number; age_bucket: "0_30" | "31_60" | "over_60" }>;
  total_outstanding_bdt: string;
  aging_bdt: { "0_30": string; "31_60": string; over_60: string };
  note: string;
};

export type OrderPnl = {
  order_id: number;
  status: string;
  created_at?: string;
  revenue_bdt: string;
  gross_collected_bdt: string;
  refunds_bdt: string;
  net_verified_cash_bdt: string;
  outstanding_bdt: string;
  purchase_orders: string[];
  supplier_cost_bdt: string;
  supplier_cost_basis: "purchase_order" | "quote";
  supplier_paid_bdt: string;
  quoted_shipping_bdt: string;
  quoted_duty_vat_bdt: string;
  estimated_margin_bdt: string;
  actual_cost_bdt: string | null;
  realized_margin_bdt: string | null;
};

export type ErpSummary = {
  orders_awaiting_purchase: number;
  purchase_orders: Record<PurchaseOrderStatus, number>;
  open_purchase_orders: number;
  payables_outstanding_bdt: string;
  payables_count: number;
  payables_over_60_bdt: string;
};

function post(body: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(body) };
}

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export function getErpSummary() { return requestJson<ErpSummary>("/api/admin/erp/summary/"); }
export function listPurchaseOrders(params: { q?: string; status?: string; page?: number; page_size?: number } = {}) {
  return requestJson<AdminListResponse<PurchaseOrder>>(`/api/admin/purchase-orders/${query(params)}`);
}
export function getPurchaseOrder(id: number | string) { return requestJson<PurchaseOrder>(`/api/admin/purchase-orders/${id}/`); }
export function createPurchaseOrder(orderId: number, payload: { unit_cost_origin?: number; note?: string } = {}) {
  return requestJson<PurchaseOrder>(`/api/admin/orders/${orderId}/purchase-orders/`, post(payload));
}
export function setPurchaseOrderStatus(id: number, status: PurchaseOrderStatus, note: string) {
  return requestJson<PurchaseOrder>(`/api/admin/purchase-orders/${id}/status/`, post({ status, note }));
}
export function addGoodsReceipt(id: number, payload: { received_qty: number; accepted_qty: number; rejected_qty: number; qc_note?: string }) {
  return requestJson<PurchaseOrder>(`/api/admin/purchase-orders/${id}/receipts/`, post(payload));
}
export function addSupplierPayment(id: number, payload: { amount_origin: number; method: string; reference?: string; note: string }) {
  return requestJson<PurchaseOrder>(`/api/admin/purchase-orders/${id}/payments/`, post(payload));
}
export function reverseSupplierPayment(paymentId: number, reason: string) {
  return requestJson<PurchaseOrder>(`/api/admin/supplier-payments/${paymentId}/reverse/`, post({ reason }));
}
export function getPayables() { return requestJson<PayablesReport>("/api/admin/finance/payables/"); }
export function getOrderPnl(page = 1, pageSize = 25) {
  return requestJson<AdminListResponse<OrderPnl>>(`/api/admin/finance/order-pnl/${query({ page, page_size: pageSize })}`);
}

export const PO_STATUS_LABELS: Record<PurchaseOrderStatus, { en: string; bn: string; tone: string }> = {
  DRAFT: { en: "Draft", bn: "খসড়া", tone: "neutral" },
  SENT: { en: "Sent to supplier", bn: "সাপ্লায়ারকে পাঠানো", tone: "pending" },
  CONFIRMED: { en: "Supplier confirmed", bn: "সাপ্লায়ার নিশ্চিত করেছে", tone: "purchased" },
  RECEIVED: { en: "Goods received", bn: "পণ্য গ্রহণ হয়েছে", tone: "in_transit" },
  CLOSED: { en: "Closed", bn: "সম্পন্ন", tone: "approved" },
  CANCELLED: { en: "Cancelled", bn: "বাতিল", tone: "cancelled" },
};
