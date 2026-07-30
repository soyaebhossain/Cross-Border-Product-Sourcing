"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminArchiveAction } from "../../../components/admin-archive-action";
import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import { AdminModal } from "../../../components/admin-modal";
import { bulkArchiveAdminEntities, createAdminSupplier, getAdminSupplier, updateAdminSupplier } from "../../../lib/admin-api";
import { getLiveCountries, type AdminSupplierRow, type Country } from "../../../lib/api";
import { useLocale } from "../../../lib/locale-context";

function countryName(country: AdminSupplierRow["country"]) { return typeof country === "string" ? country : country?.name || country?.code || "—"; }

export default function AdminSuppliersPage() {
  const [version, setVersion] = useState(0);
  const [countries, setCountries] = useState<Country[]>([]);
  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [name, setName] = useState("");
  const [countryId, setCountryId] = useState("");
  const [rating, setRating] = useState("4.00");
  const [supplierNote, setSupplierNote] = useState("");
  const [auditNote, setAuditNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { locale } = useLocale();
  const bn = locale === "bn";
  useEffect(() => { getLiveCountries().then(setCountries).catch(() => setCountries([])); }, [version]);
  const openNew = () => { setEditingId("new"); setName(""); setCountryId(countries[0] ? String(countries[0].id) : ""); setRating("4.00"); setSupplierNote(""); setAuditNote(""); setError(""); };
  const openEdit = async (row: AdminSupplierRow) => {
    setSaving(true); setError("");
    try { const item = await getAdminSupplier(row.id); setEditingId(item.id); setName(item.name); setCountryId(String(item.country.id)); setRating(String(item.rating)); setSupplierNote(item.note || ""); setAuditNote(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Supplier detail could not be loaded."); }
    finally { setSaving(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      if (editingId === "new") await createAdminSupplier({ country_id: Number(countryId), name: name.trim(), rating: Number(rating), note: supplierNote.trim() || undefined });
      else if (editingId) await updateAdminSupplier(editingId, { country_id: Number(countryId), name: name.trim(), rating: Number(rating), supplier_note: supplierNote.trim() || null, note: auditNote });
      setEditingId(null); setVersion(value => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Supplier could not be saved."); }
    finally { setSaving(false); }
  };
  const columns: AdminColumn<AdminSupplierRow>[] = [
    { key: "supplier", label: bn ? "সাপ্লায়ার" : "Supplier", cell: row => <div className="admin-primary-cell"><strong>{row.name}</strong><small>ID #{row.id}</small></div>, exportValue: row => row.name, sortValue: row => row.name },
    { key: "country", label: bn ? "দেশ" : "Country", cell: row => countryName(row.country), exportValue: row => countryName(row.country), sortValue: row => countryName(row.country) },
    { key: "rating", label: bn ? "রেটিং" : "Rating", numeric: true, cell: row => <span aria-label={`Rating ${row.rating || 0} out of 5`}>★ {Number(row.rating || 0).toFixed(2)}</span>, exportValue: row => row.rating, sortValue: row => Number(row.rating) },
    { key: "risk", label: bn ? "ঝুঁকি" : "Risk", cell: row => <span className={`admin-status admin-status--${(row.risk || "low").toLowerCase()}`}>{row.risk || "Low"}</span>, exportValue: row => row.risk || "Low", sortValue: row => row.risk || "Low" },
    { key: "offers", label: bn ? "অফার" : "Offers", numeric: true, cell: row => row.offers ?? row.offer_count ?? 0, exportValue: row => row.offers ?? row.offer_count, sortValue: row => row.offers ?? row.offer_count },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${row.is_active === false ? "inactive" : "active"}`}>{row.is_active === false ? "ARCHIVED" : "ACTIVE"}</span>, exportValue: row => row.is_active === false ? "Archived" : "Active", sortValue: row => row.is_active === false ? 0 : 1 },
  ];
  return <>
    <nav className="admin-subnav" aria-label={bn ? "Supply section" : "Supply sections"}><Link className="admin-subnav--active" href="/admin/suppliers">{bn ? "সাপ্লায়ার" : "Suppliers"}</Link><Link href="/admin/suppliers/offers">{bn ? "অফার" : "Offers"}</Link></nav>
    <AdminDataPage<AdminSupplierRow> key={version} resource="suppliers" eyebrow={bn ? "Supply network" : "Supply network"} title={bn ? "সাপ্লায়ার" : "Suppliers"} description={bn ? "Coverage, rating, risk ও offer volume পরিচালনা করুন।" : "Manage coverage, rating, sourcing risk and offer volume."} searchPlaceholder={bn ? "সাপ্লায়ার বা দেশ" : "Search supplier or country"} columns={columns} filters={[{ key: "country", label: bn ? "দেশ" : "Country", options: countries.map(country => ({ value: country.code, label: `${country.code} · ${country.name}` })) }, { key: "risk", label: bn ? "ঝুঁকি" : "Risk", options: ["Low", "Medium", "High"].map(value => ({ value, label: value })) }, { key: "active", label: bn ? "স্ট্যাটাস" : "Status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Archived" }] }]} headerAction={<button className="admin-button admin-button--primary" type="button" onClick={openNew} disabled={!countries.length}>{bn ? "সাপ্লায়ার যোগ করুন" : "Add supplier"}</button>} detailHref={row => `/admin/suppliers/${row.id}`} actions={(row, reload, notify) => <><button className="admin-row-button" type="button" onClick={() => void openEdit(row)}>Edit</button><AdminArchiveAction entity="suppliers" id={row.id} isActive={row.is_active !== false} reload={reload} notify={notify} /></>} bulkActions={[{ label: bn ? "Selected archive" : "Archive selected", kind: "danger", run: (ids, note) => bulkArchiveAdminEntities("suppliers", ids, true, note).then(() => undefined) }, { label: bn ? "Selected restore" : "Restore selected", run: (ids, note) => bulkArchiveAdminEntities("suppliers", ids, false, note).then(() => undefined) }]} />
    <AdminModal open={editingId !== null} onClose={() => !saving && setEditingId(null)} title={editingId === "new" ? (bn ? "সাপ্লায়ার যোগ করুন" : "Add supplier") : (bn ? "সাপ্লায়ার edit" : "Edit supplier")} description={bn ? "Country ID validated lookup থেকে নেওয়া হয়।" : "Country IDs come from the validated country lookup."}><form className="admin-modal__form" onSubmit={submit}><label><span>{bn ? "নাম" : "Name"}</span><input minLength={2} maxLength={120} required value={name} onChange={event => setName(event.target.value)} /></label><label><span>{bn ? "দেশ" : "Country"}</span><select required value={countryId} onChange={event => setCountryId(event.target.value)}>{countries.map(country => <option key={country.id} value={country.id}>{country.code} · {country.name}</option>)}</select></label><label><span>{bn ? "Rating (0–5)" : "Rating (0–5)"}</span><input type="number" min="0" max="5" step=".01" required value={rating} onChange={event => setRating(event.target.value)} /></label><label><span>{bn ? "Supplier note" : "Supplier note"}</span><textarea maxLength={5000} rows={3} value={supplierNote} onChange={event => setSupplierNote(event.target.value)} /></label>{editingId !== "new" ? <label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} required rows={3} value={auditNote} onChange={event => setAuditNote(event.target.value)} /></label> : null}{error ? <div className="admin-alert admin-alert--error">{error}</div> : null}<div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setEditingId(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || !countryId || !name.trim() || (editingId !== "new" && auditNote.trim().length < 3)}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div></form></AdminModal>
  </>;
}
