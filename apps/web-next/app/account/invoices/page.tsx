"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import {
  getCustomerInvoice,
  getCustomerInvoiceHtmlUrl,
  getCustomerInvoicePdfUrl,
  listCustomerInvoices,
  type CustomerInvoice,
} from "../../../lib/customer-api";
import { formatBdt, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

const pageSize = 10;

function itemText(item: Record<string, unknown>, key: string, fallback = "—") {
  const value = item[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<CustomerInvoice[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CustomerInvoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listCustomerInvoices(pageSize, offset);
      setInvoices(result.items);
      setTotal(result.total);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "ইনভয়েস লোড করা যায়নি।" : "Invoices could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, offset]);

  useEffect(() => { void load(); }, [load]);

  const openDetail = async (invoice: CustomerInvoice) => {
    setSelected(invoice);
    setDetailLoading(true);
    setError("");
    try {
      setSelected(await getCustomerInvoice(invoice.order_id));
    } catch (reason) {
      setSelected(null);
      setError(reason instanceof Error ? reason.message : (bn ? "ইনভয়েসের বিস্তারিত লোড করা যায়নি।" : "Invoice details could not be loaded."));
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div>
          <p className="eyebrow">{bn ? "বিলিং রেকর্ড" : "Billing records"}</p>
          <h1>{bn ? "ইনভয়েস" : "Invoices"}</h1>
          <p>{bn ? "প্রতিটি অর্ডারের immutable invoice snapshot দেখুন ও ডাউনলোড করুন।" : "Review and download the immutable invoice snapshot for every order."}</p>
        </div>
        <Link className="button button--ghost" href="/account/orders">{bn ? "আমার অর্ডার" : "My orders"}</Link>
      </header>

      {error ? <div className="account-alert account-alert--danger" role="alert"><span>{error}</span><button type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}

      <section className="account-panel">
        <div className="account-panel__header">
          <div><h2>{bn ? "জারি করা ইনভয়েস" : "Issued invoices"}</h2><p>{bn ? `${total}টি রেকর্ড` : `${total} record${total === 1 ? "" : "s"}`}</p></div>
        </div>
        {loading ? <div className="empty-state" aria-live="polite">{bn ? "ইনভয়েস লোড হচ্ছে…" : "Loading invoices…"}</div> : invoices.length ? (
          <div className="account-list">
            {invoices.map(invoice => (
              <article className="account-list__row" key={invoice.id}>
                <div>
                  <strong>{invoice.invoice_number} · {bn ? "অর্ডার" : "Order"} #{invoice.order_id}</strong>
                  <span>{formatDateTime(invoice.issued_at || invoice.created_at, intlLocale)} · {invoice.status} · {invoice.payment_status}</span>
                </div>
                <strong>{formatBdt(invoice.total_bdt, intlLocale)}</strong>
                <div className="account-inline-actions">
                  <button className="button button--ghost" type="button" onClick={() => void openDetail(invoice)}>{bn ? "দেখুন" : "View"}</button>
                  <a className="button button--ghost" href={getCustomerInvoicePdfUrl(invoice.order_id)}>{bn ? "PDF (ল্যাটিন)" : "PDF (Latin)"}</a>
                  <a className="button button--ghost" href={getCustomerInvoiceHtmlUrl(invoice.order_id)}>{bn ? "প্রিন্টযোগ্য বাংলা/English" : "Printable বাংলা/English"}</a>
                </div>
              </article>
            ))}
          </div>
        ) : <div className="empty-state"><strong>{bn ? "এখনো কোনো ইনভয়েস নেই" : "No invoices yet"}</strong><span>{bn ? "অর্ডার তৈরি হলে invoice snapshot এখানে দেখা যাবে।" : "An invoice snapshot appears here after an order is created."}</span></div>}
        {total > pageSize ? <div className="account-pagination">
          <button className="button button--ghost" type="button" disabled={offset === 0 || loading} onClick={() => setOffset(current => Math.max(0, current - pageSize))}>{bn ? "আগের" : "Previous"}</button>
          <span>{bn ? `${offset + 1}–${Math.min(offset + pageSize, total)} / ${total}` : `${offset + 1}–${Math.min(offset + pageSize, total)} of ${total}`}</span>
          <button className="button button--ghost" type="button" disabled={offset + pageSize >= total || loading} onClick={() => setOffset(current => current + pageSize)}>{bn ? "পরের" : "Next"}</button>
        </div> : null}
      </section>

      <AdminModal
        open={selected !== null}
        onClose={() => !detailLoading && setSelected(null)}
        title={selected ? selected.invoice_number : (bn ? "ইনভয়েস" : "Invoice")}
        description={selected ? `${bn ? "অর্ডার" : "Order"} #${selected.order_id} · ${selected.status}` : undefined}
      >
        {selected ? <div className="account-invoice-detail">
          {detailLoading ? <div className="empty-state" aria-live="polite">{bn ? "বিস্তারিত লোড হচ্ছে…" : "Loading details…"}</div> : <>
            <dl className="account-definition-list">
              <div><dt>{bn ? "মোট" : "Total"}</dt><dd>{formatBdt(selected.total_bdt, intlLocale)}</dd></div>
              <div><dt>{bn ? "শিপিং" : "Shipping"}</dt><dd>{formatBdt(selected.shipping_bdt, intlLocale)}</dd></div>
              <div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatBdt(selected.advance_bdt, intlLocale)}</dd></div>
              <div><dt>{bn ? "বাকি" : "Remaining"}</dt><dd>{formatBdt(selected.remaining_bdt, intlLocale)}</dd></div>
              <div><dt>{bn ? "পেমেন্ট" : "Payment"}</dt><dd>{selected.payment_status}</dd></div>
            </dl>
            <div className="account-invoice-items">
              <h3>{bn ? "পণ্য" : "Items"}</h3>
              {selected.items.length ? selected.items.map((item, index) => <div key={`${itemText(item, "variant_id", String(index))}-${index}`}><span>{itemText(item, "product_name", itemText(item, "name", bn ? "পণ্য" : "Item"))}{itemText(item, "variant_name") !== "—" ? ` · ${itemText(item, "variant_name")}` : ""}</span><strong>× {itemText(item, "qty", "1")}</strong></div>) : <p>{bn ? "কোনো item snapshot নেই।" : "No item snapshot is available."}</p>}
            </div>
            <div className="admin-modal__actions">
              <a className="admin-button admin-button--secondary" href={getCustomerInvoicePdfUrl(selected.order_id)}>{bn ? "PDF (ল্যাটিন)" : "PDF (Latin)"}</a>
              <a className="admin-button admin-button--primary" href={getCustomerInvoiceHtmlUrl(selected.order_id)}>{bn ? "প্রিন্টযোগ্য বাংলা/English" : "Printable বাংলা/English"}</a>
            </div>
          </>}
        </div> : null}
      </AdminModal>
    </div>
  );
}
