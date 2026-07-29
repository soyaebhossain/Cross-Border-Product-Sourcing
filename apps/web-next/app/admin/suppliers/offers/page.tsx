"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminArchiveAction } from "../../../../components/admin-archive-action";
import { AdminDataPage, type AdminColumn } from "../../../../components/admin-data-page";
import { AdminModal } from "../../../../components/admin-modal";
import {
  bulkArchiveAdminEntities,
  createAdminOffer,
  getAdminOffer,
  getAdminSupplier,
  listAdminVariants,
  updateAdminOffer,
  type AdminOffer,
  type AdminSupplier,
  type AdminVariant,
} from "../../../../lib/admin-api";
import { getAdminList, getCountries, type AdminSupplierRow, type Country } from "../../../../lib/api";
import { formatAmount, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

type Fields = { variant_id: string; seller_id: string; country_id: string; mode: "LOCAL" | "BULK"; price_origin: string; currency: string; stock: string; moq: string; source_url: string };
const blank: Fields = { variant_id: "", seller_id: "", country_id: "", mode: "LOCAL", price_origin: "", currency: "USD", stock: "0", moq: "1", source_url: "" };

export default function AdminOffersPage() {
  const [version, setVersion] = useState(0);
  const [suppliers, setSuppliers] = useState<AdminSupplier[]>([]);
  const [variants, setVariants] = useState<AdminVariant[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [fields, setFields] = useState<Fields>(blank);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  useEffect(() => {
    Promise.all([getAdminList<AdminSupplierRow>("suppliers", { page_size: 100 }), listAdminVariants({ page_size: 100, active: true }), getCountries()])
      .then(async ([supplierPage, variantPage, countryRows]) => {
        const details = await Promise.all(supplierPage.items.filter(item => item.is_active !== false).map(item => getAdminSupplier(item.id)));
        setSuppliers(details); setVariants(variantPage.items); setCountries(countryRows);
      }).catch(() => { setSuppliers([]); setVariants([]); setCountries([]); });
  }, [version]);
  const set = (key: keyof Fields, value: string) => setFields(current => ({ ...current, [key]: value }));
  const openNew = () => {
    const supplier = suppliers[0];
    setEditingId("new"); setFields({ ...blank, variant_id: variants[0] ? String(variants[0].id) : "", seller_id: supplier ? String(supplier.id) : "", country_id: supplier ? String(supplier.country.id) : countries[0] ? String(countries[0].id) : "" }); setNote(""); setError("");
  };
  const openEdit = async (row: AdminOffer) => {
    setSaving(true); setError("");
    try { const item = await getAdminOffer(row.id); setEditingId(item.id); setFields({ variant_id: String(item.variant.id), seller_id: String(item.supplier.id), country_id: String(item.country.id), mode: item.mode, price_origin: item.price_origin, currency: item.currency, stock: String(item.stock), moq: String(item.moq), source_url: item.source_url || "" }); setNote(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Offer could not be loaded."); }
    finally { setSaving(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    const payload = { variant_id: Number(fields.variant_id), seller_id: Number(fields.seller_id), country_id: Number(fields.country_id), mode: fields.mode, price_origin: Number(fields.price_origin), currency: fields.currency.trim().toUpperCase(), stock: Number(fields.stock), moq: Number(fields.moq), source_url: fields.source_url.trim() || undefined };
    try {
      if (editingId === "new") await createAdminOffer(payload);
      else if (editingId) await updateAdminOffer(editingId, { ...payload, note });
      setEditingId(null); setVersion(value => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Offer could not be saved."); }
    finally { setSaving(false); }
  };
  const columns: AdminColumn<AdminOffer>[] = [
    { key: "offer", label: bn ? "অফার" : "Offer", cell: row => <div className="admin-primary-cell"><strong>{row.variant.product_name}</strong><small>{row.variant.name || row.variant.sku || `Variant #${row.variant.id}`}</small></div>, exportValue: row => `${row.variant.product_name} ${row.variant.name || ""}`, sortValue: row => row.variant.product_name },
    { key: "supplier", label: bn ? "সাপ্লায়ার" : "Supplier", cell: row => row.supplier.name, exportValue: row => row.supplier.name, sortValue: row => row.supplier.name },
    { key: "route", label: bn ? "রুট" : "Route", cell: row => `${row.country.code} · ${row.mode}`, exportValue: row => `${row.country.code} ${row.mode}`, sortValue: row => row.country.code },
    { key: "price", label: bn ? "মূল্য" : "Origin price", numeric: true, cell: row => `${row.currency} ${formatAmount(row.price_origin)}`, exportValue: row => `${row.currency} ${row.price_origin}`, sortValue: row => Number(row.price_origin) },
    { key: "stock", label: bn ? "Stock / MOQ" : "Stock / MOQ", numeric: true, cell: row => `${row.stock} / ${row.moq}`, exportValue: row => `${row.stock}/${row.moq}`, sortValue: row => row.stock },
    { key: "updated", label: bn ? "আপডেট" : "Updated", cell: row => formatDateTime(row.updated_at, intlLocale), exportValue: row => row.updated_at, sortValue: row => row.updated_at },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "ACTIVE" : "ARCHIVED"}</span>, exportValue: row => row.is_active ? "Active" : "Archived", sortValue: row => row.is_active ? 1 : 0 },
  ];
  return <>
    <nav className="admin-subnav" aria-label={bn ? "Supply section" : "Supply sections"}><Link href="/admin/suppliers">{bn ? "সাপ্লায়ার" : "Suppliers"}</Link><Link className="admin-subnav--active" href="/admin/suppliers/offers">{bn ? "অফার" : "Offers"}</Link></nav>
    <AdminDataPage<AdminOffer> key={version} resource="offers" eyebrow={bn ? "Supplier marketplace" : "Supplier marketplace"} title={bn ? "সাপ্লায়ার অফার" : "Supplier offers"} description={bn ? "Variant price, stock, MOQ, mode ও source URL পরিচালনা করুন।" : "Manage variant pricing, stock, MOQ, mode and source URLs."} searchPlaceholder={bn ? "পণ্য, variant, supplier বা SKU" : "Search product, variant, supplier or SKU"} columns={columns} filters={[{ key: "country", label: bn ? "দেশ" : "Country", options: countries.map(country => ({ value: country.code, label: country.code })) }, { key: "mode", label: "Mode", options: ["LOCAL", "BULK"].map(value => ({ value, label: value })) }, { key: "active", label: bn ? "স্ট্যাটাস" : "Status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Archived" }] }]} headerAction={<button className="admin-button admin-button--primary" type="button" disabled={!suppliers.length || !variants.length} onClick={openNew}>{bn ? "অফার যোগ করুন" : "Add offer"}</button>} detailHref={row => `/admin/suppliers/offers/${row.id}`} actions={(row, reload, notify) => <><button className="admin-row-button" type="button" onClick={() => void openEdit(row)}>Edit</button><AdminArchiveAction entity="offers" id={row.id} isActive={row.is_active} reload={reload} notify={notify} /></>} bulkActions={[{ label: bn ? "Selected archive" : "Archive selected", kind: "danger", run: (ids, auditNote) => bulkArchiveAdminEntities("offers", ids, true, auditNote).then(() => undefined) }, { label: bn ? "Selected restore" : "Restore selected", run: (ids, auditNote) => bulkArchiveAdminEntities("offers", ids, false, auditNote).then(() => undefined) }]} />
    <AdminModal open={editingId !== null} onClose={() => !saving && setEditingId(null)} title={editingId === "new" ? (bn ? "অফার যোগ করুন" : "Add offer") : (bn ? "অফার edit" : "Edit offer")} description={bn ? "Supplier, variant এবং country backend-এ active-link validation পায়।" : "Supplier, variant and country links are validated by the backend."}><form className="admin-modal__form" onSubmit={submit}><label><span>{bn ? "ভ্যারিয়েন্ট" : "Variant"}</span><select required value={fields.variant_id} onChange={event => set("variant_id", event.target.value)}>{variants.map(item => <option value={item.id} key={item.id}>{item.product_name} · {item.variant_name || item.sku || `#${item.id}`}</option>)}</select></label><label><span>{bn ? "সাপ্লায়ার" : "Supplier"}</span><select required value={fields.seller_id} onChange={event => { set("seller_id", event.target.value); const selected = suppliers.find(item => item.id === Number(event.target.value)); if (selected) set("country_id", String(selected.country.id)); }}>{suppliers.map(item => <option value={item.id} key={item.id}>{item.name} · {item.country.code}</option>)}</select></label><div className="admin-form-grid"><label><span>{bn ? "দেশ" : "Country"}</span><select required value={fields.country_id} onChange={event => set("country_id", event.target.value)}>{countries.map(country => <option key={country.id} value={country.id}>{country.code}</option>)}</select></label><label><span>Mode</span><select value={fields.mode} onChange={event => set("mode", event.target.value as "LOCAL" | "BULK")}><option>LOCAL</option><option>BULK</option></select></label><label><span>{bn ? "মূল্য" : "Price"}</span><input type="number" min=".0001" step=".0001" required value={fields.price_origin} onChange={event => set("price_origin", event.target.value)} /></label><label><span>{bn ? "মুদ্রা" : "Currency"}</span><input pattern="[A-Za-z]+" minLength={3} maxLength={10} required value={fields.currency} onChange={event => set("currency", event.target.value)} /></label><label><span>Stock</span><input type="number" min="0" required value={fields.stock} onChange={event => set("stock", event.target.value)} /></label><label><span>MOQ</span><input type="number" min="1" required value={fields.moq} onChange={event => set("moq", event.target.value)} /></label></div><label><span>Source URL</span><input type="url" maxLength={500} value={fields.source_url} onChange={event => set("source_url", event.target.value)} /></label>{editingId !== "new" ? <label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} required rows={3} value={note} onChange={event => setNote(event.target.value)} /></label> : null}{error ? <div className="admin-alert admin-alert--error">{error}</div> : null}<div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setEditingId(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || !fields.variant_id || !fields.seller_id || !fields.country_id || Number(fields.price_origin) <= 0 || (editingId !== "new" && note.trim().length < 3)}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div></form></AdminModal>
  </>;
}
