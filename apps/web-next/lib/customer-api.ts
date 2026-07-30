import { requestJson, requestVoid } from "./api";

const customerApiBase = "";

export type Paged<T> = { items: T[]; total: number; limit: number; offset: number };

export type CustomerProfile = {
  user_id: number;
  username?: string | null;
  email?: string | null;
  phone?: string | null;
  full_name?: string | null;
  company: { name?: string | null; registration_number?: string | null; tax_identifier?: string | null };
  preferences: { language: "en" | "bn"; currency: string; timezone: string };
  created_at?: string;
  updated_at?: string;
};

export type CustomerAddress = {
  id: number;
  label: string;
  recipient_name: string;
  company_name?: string | null;
  line1: string;
  line2?: string | null;
  city: string;
  region?: string | null;
  postal_code?: string | null;
  country_code: string;
  phone: string;
  is_default_shipping: boolean;
  is_default_billing: boolean;
  created_at?: string;
  updated_at?: string;
};

export type AddressPayload = Omit<CustomerAddress, "id" | "created_at" | "updated_at">;

export type CustomerInvoice = {
  id: number;
  invoice_number: string;
  order_id: number;
  issued_at?: string;
  currency: string;
  status: string;
  payment_status: string;
  customer_id: number;
  customer?: Record<string, unknown> | null;
  shipping_address?: Record<string, unknown> | null;
  billing_address?: Record<string, unknown> | null;
  country_code?: string;
  items: Array<Record<string, unknown>>;
  total_bdt: string;
  shipping_bdt: string;
  advance_bdt: string;
  remaining_bdt: string;
  gross_collected_bdt?: string;
  refunds_bdt?: string;
  net_verified_cash_bdt?: string;
  outstanding_bdt?: string;
  created_at?: string;
  updated_at?: string;
};

export type NotificationPreferences = {
  order_email: boolean;
  order_sms: boolean;
  order_whatsapp: boolean;
  support_email: boolean;
  support_sms: boolean;
  support_whatsapp: boolean;
  marketing_email: boolean;
  updated_at?: string;
};

export type NotificationDelivery = {
  id: number;
  channel: string;
  destination_masked?: string | null;
  status: string;
  attempts: number;
  next_attempt_at?: string | null;
  last_attempt_at?: string | null;
  sent_at?: string | null;
  provider_message_id?: string | null;
  error_code?: string | null;
  error_detail?: string | null;
  created_at?: string;
};

export type CustomerNotification = {
  id: number;
  order_id?: number | null;
  category: string;
  title: string;
  body: string;
  data?: Record<string, unknown> | null;
  read_at?: string | null;
  created_at?: string;
  deliveries: NotificationDelivery[];
};

export type SupportMessage = {
  id: number;
  author_user_id: number;
  author_role: string;
  body: string;
  request_id?: string | null;
  created_at?: string;
};

export type SupportTicket = {
  id: number;
  public_id: string;
  user_id: number;
  order_id?: number | null;
  subject: string;
  category: string;
  priority: string;
  status: string;
  resolved_at?: string | null;
  closed_at?: string | null;
  created_at?: string;
  updated_at?: string;
  messages?: SupportMessage[];
};

export type CustomerDispute = {
  id: number;
  public_id: string;
  user_id: number;
  order_id: number;
  type: string;
  description: string;
  requested_resolution: string;
  status: string;
  resolution_note?: string | null;
  decided_by_user_id?: number | null;
  request_id?: string | null;
  decided_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type PaymentAttempt = {
  id: number;
  payment_id: number;
  order_id: number;
  attempt_number: number;
  channel: string;
  trx_id: string;
  screenshot_url?: string | null;
  submitted_by_user_id: number;
  request_id?: string | null;
  created_at?: string;
  decisions: Array<{ id: number; decision: string; reason?: string | null; actor_user_id?: number | null; actor_role: string; request_id?: string | null; created_at?: string }>;
};

function json(method: string, payload?: unknown): RequestInit {
  return { method, ...(payload === undefined ? {} : { body: JSON.stringify(payload) }) };
}

function query(params: Record<string, string | number | boolean | undefined>) {
  const value = new URLSearchParams();
  Object.entries(params).forEach(([key, item]) => {
    if (item !== undefined && item !== "") value.set(key, String(item));
  });
  const encoded = value.toString();
  return encoded ? `?${encoded}` : "";
}

export function getCustomerProfile() { return requestJson<CustomerProfile>("/api/account/profile/"); }
export function updateCustomerProfile(payload: Partial<{ full_name: string | null; company_name: string | null; company_registration_number: string | null; tax_identifier: string | null; preferred_language: "en" | "bn"; preferred_currency: string; timezone: string }>) { return requestJson<CustomerProfile>("/api/account/profile/", json("PATCH", payload)); }
export function listCustomerAddresses() { return requestJson<CustomerAddress[]>("/api/account/addresses/"); }
export function createCustomerAddress(payload: AddressPayload) { return requestJson<CustomerAddress>("/api/account/addresses/", json("POST", payload)); }
export function updateCustomerAddress(id: number, payload: Partial<AddressPayload>) { return requestJson<CustomerAddress>(`/api/account/addresses/${id}/`, json("PATCH", payload)); }
export function deleteCustomerAddress(id: number) { return requestVoid(`/api/account/addresses/${id}/`, json("DELETE")); }

export function listCustomerInvoices(limit = 25, offset = 0) { return requestJson<Paged<CustomerInvoice>>(`/api/account/invoices/${query({ limit, offset })}`); }
export function getCustomerInvoice(orderId: number | string) { return requestJson<CustomerInvoice>(`/api/account/invoices/${orderId}/`); }
export function getCustomerInvoicePdfUrl(orderId: number | string) { return `${customerApiBase}/api/account/invoices/${orderId}/pdf/`; }
export function getCustomerInvoiceHtmlUrl(orderId: number | string) { return `${customerApiBase}/api/account/invoices/${orderId}/download/`; }

export function getNotificationPreferences() { return requestJson<NotificationPreferences>("/api/account/notification-preferences/"); }
export function updateNotificationPreferences(payload: Partial<Omit<NotificationPreferences, "updated_at">>) { return requestJson<NotificationPreferences>("/api/account/notification-preferences/", json("PATCH", payload)); }
export function listCustomerNotifications(params: { unread_only?: boolean; limit?: number; offset?: number } = {}) { return requestJson<Paged<CustomerNotification>>(`/api/account/notifications/${query({ limit: 25, offset: 0, ...params })}`); }
export function markCustomerNotificationRead(id: number) { return requestJson<CustomerNotification>(`/api/account/notifications/${id}/read/`, json("POST", {})); }
export function markAllCustomerNotificationsRead() { return requestJson<{ updated: number }>("/api/account/notifications/read-all/", json("POST", {})); }

export function listCustomerSupportTickets(params: { status?: string; limit?: number; offset?: number } = {}) { return requestJson<Paged<SupportTicket>>(`/api/account/support-tickets/${query({ limit: 25, offset: 0, ...params })}`); }
export function createCustomerSupportTicket(payload: { subject: string; category: string; priority: string; message: string; order_id?: number }) { return requestJson<SupportTicket>("/api/account/support-tickets/", json("POST", payload)); }
export function getCustomerSupportTicket(id: number | string) { return requestJson<SupportTicket>(`/api/account/support-tickets/${id}/`); }
export function addCustomerSupportMessage(id: number, body: string) { return requestJson<SupportTicket>(`/api/account/support-tickets/${id}/messages/`, json("POST", { body })); }

export function listCustomerDisputes(limit = 25, offset = 0) { return requestJson<Paged<CustomerDispute>>(`/api/account/disputes/${query({ limit, offset })}`); }
export function createCustomerDispute(payload: { order_id: number; dispute_type: string; description: string; requested_resolution: string }) { return requestJson<CustomerDispute>("/api/account/disputes/", json("POST", payload)); }
export function getCustomerDispute(id: number | string) { return requestJson<CustomerDispute>(`/api/account/disputes/${id}/`); }
export function cancelCustomerDispute(id: number, note: string) { return requestJson<CustomerDispute>(`/api/account/disputes/${id}/cancel/`, json("POST", { note })); }

export function listPaymentAttempts(orderId: number | string) { return requestJson<PaymentAttempt[]>(`/api/account/orders/${orderId}/payment-attempts/`); }
export function retryCustomerPayment(orderId: number, payload: { channel: "bKash" | "Nagad" | "Rocket" | "Bank"; trx_id: string; screenshot_url?: string }) { return requestJson<{ order_id: number; order_status: string; payment_status: string; attempt: PaymentAttempt }>(`/api/account/orders/${orderId}/payment-retry/`, json("POST", payload)); }

export function listAdminSupportTickets(params: { q?: string; status?: string; limit?: number; offset?: number } = {}) { return requestJson<Paged<SupportTicket>>(`/api/admin/support-tickets/${query({ limit: 25, offset: 0, ...params })}`); }
export function getAdminSupportTicket(id: number | string) { return requestJson<SupportTicket>(`/api/admin/support-tickets/${id}/`); }
export function addAdminSupportMessage(id: number, body: string) { return requestJson<SupportTicket>(`/api/admin/support-tickets/${id}/messages/`, json("POST", { body })); }
export function updateAdminSupportStatus(id: number, status: string, note: string) { return requestJson<SupportTicket>(`/api/admin/support-tickets/${id}/status/`, json("PATCH", { status, note })); }

export function listAdminDisputes(params: { q?: string; status?: string; limit?: number; offset?: number } = {}) { return requestJson<Paged<CustomerDispute>>(`/api/admin/disputes/${query({ limit: 25, offset: 0, ...params })}`); }
export function getAdminDispute(id: number | string) { return requestJson<CustomerDispute>(`/api/admin/disputes/${id}/`); }
export function updateAdminDispute(id: number, status: string, note: string) { return requestJson<CustomerDispute>(`/api/admin/disputes/${id}/`, json("PATCH", { status, note })); }

export function listAdminOutbox(params: { status?: string; channel?: string; limit?: number; offset?: number } = {}) { return requestJson<Paged<NotificationDelivery>>(`/api/admin/notifications/outbox/${query({ limit: 25, offset: 0, ...params })}`); }
export function getAdminOutbox(id: number | string) { return requestJson<NotificationDelivery>(`/api/admin/notifications/outbox/${id}/`); }
export function requeueAdminOutbox(id: number) { return requestJson<NotificationDelivery>(`/api/admin/notifications/outbox/${id}/requeue/`, json("POST", {})); }
export function dispatchAdminOutbox() { return requestJson<Record<string, number>>("/api/admin/notifications/outbox/dispatch/?limit=1", json("POST", {})); }
