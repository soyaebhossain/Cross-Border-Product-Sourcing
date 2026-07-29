"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import {
  archiveAdminSetting,
  getAdminSettings,
  saveAdminSetting,
  type AdminSettings,
} from "../../../lib/admin-api";
import { getCategories, getCountries, type Category, type Country } from "../../../lib/api";
import { formatAmount, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

type RuleType = "currencies" | "service-fees" | "shipping-rates" | "eta-rules" | "duty-rules";
type SettingsKey = keyof AdminSettings;
type RuleRow =
  | AdminSettings["currencies"][number]
  | AdminSettings["service_fees"][number]
  | AdminSettings["shipping_rates"][number]
  | AdminSettings["eta_rules"][number]
  | AdminSettings["duty_rules"][number];

const tabs: Array<{ type: RuleType; key: SettingsKey; label: string }> = [
  { type: "currencies", key: "currencies", label: "Currency" },
  { type: "service-fees", key: "service_fees", label: "Service fees" },
  { type: "shipping-rates", key: "shipping_rates", label: "Shipping" },
  { type: "eta-rules", key: "eta_rules", label: "ETA" },
  { type: "duty-rules", key: "duty_rules", label: "Duty" },
];

function rowSummary(row: RuleRow) {
  if ("currency" in row) return row.currency;
  if ("fee_bdt" in row) return `${row.mode} service fee`;
  if ("method" in row) return `${row.country} · ${row.method}`;
  if ("delivery_type" in row) return `${row.country} · ${row.mode} · ${row.delivery_type}`;
  return `${row.country} · ${row.category || "All categories"}`;
}

function rowValue(row: RuleRow, intlLocale: string) {
  if ("currency" in row) return `৳${formatAmount(row.rate_to_bdt, intlLocale)} / ${row.currency}`;
  if ("fee_bdt" in row) return `৳${formatAmount(row.fee_bdt, intlLocale)} + ${formatAmount(row.percent, intlLocale)}%`;
  if ("method" in row) return `${row.min_kg}–${row.max_kg} kg · ৳${formatAmount(row.cost_bdt, intlLocale)}`;
  if ("delivery_type" in row) return `${row.min_days}–${row.max_days} days`;
  return `${formatAmount(row.percent, intlLocale)}% + ৳${formatAmount(row.fixed_bdt, intlLocale)}`;
}

function blankFields(type: RuleType, countries: Country[], categories: Category[]): Record<string, string> {
  const country = countries[0] ? String(countries[0].id) : "";
  if (type === "currencies") return { currency: "USD", rate_to_bdt: "" };
  if (type === "service-fees") return { mode: "LOCAL", fee_bdt: "0", percent: "0" };
  if (type === "shipping-rates") return { country_id: country, method: "AIR", min_kg: "0", max_kg: "1", cost_bdt: "0" };
  if (type === "eta-rules") return { country_id: country, mode: "LOCAL", delivery_type: "DOOR", min_days: "0", max_days: "7" };
  return { country_id: country, category_id: categories[0] ? String(categories[0].id) : "", percent: "0", fixed_bdt: "0", effective_from: "", effective_to: "" };
}

function fieldsFromRow(type: RuleType, row: RuleRow): Record<string, string> {
  if (type === "currencies" && "currency" in row) return { currency: row.currency, rate_to_bdt: row.rate_to_bdt };
  if (type === "service-fees" && "fee_bdt" in row) return { mode: row.mode, fee_bdt: row.fee_bdt, percent: row.percent };
  if (type === "shipping-rates" && "method" in row) return { country_id: String(row.country_id), method: row.method, min_kg: row.min_kg, max_kg: row.max_kg, cost_bdt: row.cost_bdt };
  if (type === "eta-rules" && "delivery_type" in row) return { country_id: String(row.country_id), mode: row.mode, delivery_type: row.delivery_type, min_days: String(row.min_days), max_days: String(row.max_days) };
  if (type === "duty-rules" && "fixed_bdt" in row && !("fee_bdt" in row)) return { country_id: String(row.country_id), category_id: row.category_id ? String(row.category_id) : "", percent: row.percent, fixed_bdt: row.fixed_bdt, effective_from: row.effective_from?.slice(0, 16) || "", effective_to: row.effective_to?.slice(0, 16) || "" };
  return {};
}

function csvEscape(value: unknown) {
  return `"${String(value ?? "").replaceAll("\"", "\"\"")}"`;
}

export default function AdminRulesPage() {
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [countries, setCountries] = useState<Country[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [type, setType] = useState<RuleType>("currencies");
  const [editing, setEditing] = useState<RuleRow | "new" | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [archiveTarget, setArchiveTarget] = useState<{ row: RuleRow; archived: boolean } | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkArchived, setBulkArchived] = useState<boolean | null>(null);
  const [q, setQ] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ message: string; kind: "success" | "error" } | null>(null);
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextSettings, nextCountries, nextCategories] = await Promise.all([getAdminSettings(), getCountries(), getCategories()]);
      setSettings(nextSettings);
      setCountries(nextCountries);
      setCategories(nextCategories);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "রুল ডেটা লোড করা যায়নি।" : "Rules could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn]);

  useEffect(() => { void load(); }, [load]);

  const tab = tabs.find(item => item.type === type) || tabs[0];
  const rows = useMemo(() => (settings?.[tab.key] || []) as RuleRow[], [settings, tab.key]);
  const filtered = useMemo(() => rows.filter(row => {
    const text = `${rowSummary(row)} ${rowValue(row, intlLocale)}`.toLowerCase();
    if (q && !text.includes(q.toLowerCase())) return false;
    if (activeFilter && String(row.is_active) !== activeFilter) return false;
    const updated = row.updated_at?.slice(0, 10) || "";
    if (dateFrom && (!updated || updated < dateFrom)) return false;
    if (dateTo && (!updated || updated > dateTo)) return false;
    return true;
  }).sort((left, right) => sortDirection === "asc" ? rowSummary(left).localeCompare(rowSummary(right), intlLocale) : rowSummary(right).localeCompare(rowSummary(left), intlLocale)), [activeFilter, dateFrom, dateTo, intlLocale, q, rows, sortDirection]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visibleRows = filtered.slice((Math.min(page, pages) - 1) * pageSize, Math.min(page, pages) * pageSize);
  const allSelected = visibleRows.length > 0 && visibleRows.every(row => selected.has(row.id));

  const notify = (message: string, kind: "success" | "error" = "success") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), 3600);
  };
  const setField = (key: string, value: string) => setFields(current => ({ ...current, [key]: value }));
  const switchType = (next: RuleType) => {
    setType(next); setPage(1); setSelected(new Set()); setQ(""); setActiveFilter(""); setDateFrom(""); setDateTo("");
  };
  const openNew = () => { setEditing("new"); setFields(blankFields(type, countries, categories)); setNote(""); setError(""); };
  const openEdit = (row: RuleRow) => { setEditing(row); setFields(fieldsFromRow(type, row)); setNote(""); setError(""); };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      let payload: Record<string, unknown>;
      if (type === "currencies") payload = { currency: fields.currency.trim().toUpperCase(), rate_to_bdt: Number(fields.rate_to_bdt), note };
      else if (type === "service-fees") payload = { mode: fields.mode, fee_bdt: Number(fields.fee_bdt), percent: Number(fields.percent), note };
      else if (type === "shipping-rates") payload = { country_id: Number(fields.country_id), method: fields.method, min_kg: Number(fields.min_kg), max_kg: Number(fields.max_kg), cost_bdt: Number(fields.cost_bdt), note };
      else if (type === "eta-rules") payload = { country_id: Number(fields.country_id), mode: fields.mode, delivery_type: fields.delivery_type, min_days: Number(fields.min_days), max_days: Number(fields.max_days), note };
      else payload = { country_id: Number(fields.country_id), category_id: fields.category_id ? Number(fields.category_id) : null, percent: Number(fields.percent), fixed_bdt: Number(fields.fixed_bdt), effective_from: fields.effective_from ? `${fields.effective_from}:00+06:00` : null, effective_to: fields.effective_to ? `${fields.effective_to}:00+06:00` : null, note };
      await saveAdminSetting(type, payload, editing === "new" ? undefined : editing?.id);
      setEditing(null);
      setNote("");
      notify(bn ? "রুল audit log-সহ সংরক্ষিত হয়েছে।" : "Rule saved with an audit record.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "রুল সংরক্ষণ করা যায়নি।" : "Rule could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  const archiveOne = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!archiveTarget) return;
    setSaving(true);
    try {
      await archiveAdminSetting(type, archiveTarget.row.id, archiveTarget.archived, note);
      setArchiveTarget(null); setNote("");
      notify(archiveTarget.archived ? (bn ? "রুল archive হয়েছে।" : "Rule archived.") : (bn ? "রুল restore হয়েছে।" : "Rule restored."));
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "রুল পরিবর্তন করা যায়নি।" : "Rule could not be changed."));
    } finally {
      setSaving(false);
    }
  };

  const archiveMany = async (event: React.FormEvent) => {
    event.preventDefault();
    if (bulkArchived === null) return;
    setSaving(true);
    try {
      await Promise.all([...selected].map(id => archiveAdminSetting(type, id, bulkArchived, note)));
      notify(bn ? `${selected.size}টি রুল audit log-সহ পরিবর্তিত হয়েছে।` : `${selected.size} rules changed with audit records.`);
      setBulkArchived(null); setSelected(new Set()); setNote("");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "এক বা একাধিক রুল পরিবর্তন করা যায়নি; refresh করে অবস্থা যাচাই করুন।" : "One or more rules could not be changed; refresh to verify the current state."));
    } finally {
      setSaving(false);
    }
  };

  const exportCsv = () => {
    const exportRows = selected.size ? filtered.filter(row => selected.has(row.id)) : filtered;
    if (!exportRows.length) return;
    const csv = [["ID", "Rule", "Value", "Status", "Updated"].map(csvEscape).join(","), ...exportRows.map(row => [row.id, rowSummary(row), rowValue(row, intlLocale), row.is_active ? "Active" : "Archived", row.updated_at].map(csvEscape).join(","))].join("\r\n");
    const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = `sourceai-${type}-${new Date().toISOString().slice(0, 10)}.csv`; link.click();
    URL.revokeObjectURL(url);
  };

  if (loading && !settings) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "অপারেশন রুল লোড হচ্ছে…" : "Loading operational rules…"}</div>;
  return <div className="admin-page">
    <header className="admin-page-header">
      <div><p className="admin-eyebrow">{bn ? "গ্লোবাল অপারেশন কনফিগারেশন" : "Global operations configuration"}</p><h1>{bn ? "Shipping, currency ও duty rules" : "Shipping, currency and duty rules"}</h1><p>{bn ? "Price calculation ও delivery estimate-এ ব্যবহৃত server-side rules পরিচালনা করুন।" : "Manage the server-side rules used in price calculation and delivery estimates."}</p></div>
      <div className="admin-toolbar"><button className="admin-button admin-button--secondary" type="button" disabled={!filtered.length} onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button><button className="admin-button admin-button--secondary" type="button" disabled={!filtered.length} onClick={exportCsv}>{bn ? "CSV এক্সপোর্ট" : "Export CSV"}</button><button className="admin-button admin-button--primary" type="button" onClick={openNew}>{bn ? "রুল যোগ করুন" : "Add rule"}</button></div>
    </header>

    <nav className="admin-subnav" aria-label={bn ? "রুলের ধরন" : "Rule types"}>{tabs.map(item => <button key={item.type} type="button" className={type === item.type ? "admin-subnav--active" : ""} onClick={() => switchType(item.type)}>{item.label}</button>)}</nav>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "অপারেশন ব্যর্থ" : "Operation failed"}</strong><span>{error}</span><button type="button" onClick={() => { setError(""); void load(); }}>{bn ? "রিফ্রেশ" : "Refresh"}</button></div> : null}

    <section className="admin-card admin-list-card">
      <div className="admin-list-toolbar">
        <label className="admin-search"><span className="sr-only">{bn ? "খুঁজুন" : "Search"}</span><input value={q} onChange={event => { setQ(event.target.value); setPage(1); }} placeholder={bn ? "Rule খুঁজুন" : "Search rules"} /></label>
        <label className="admin-filter"><span>{bn ? "অবস্থা" : "Status"}</span><select value={activeFilter} onChange={event => { setActiveFilter(event.target.value); setPage(1); }}><option value="">{bn ? "সব" : "All"}</option><option value="true">Active</option><option value="false">Archived</option></select></label>
        <div className="admin-date-range"><label className="admin-filter"><span>{bn ? "শুরু" : "From"}</span><input type="date" value={dateFrom} max={dateTo || undefined} onChange={event => { setDateFrom(event.target.value); setPage(1); }} /></label><label className="admin-filter"><span>{bn ? "শেষ" : "To"}</span><input type="date" value={dateTo} min={dateFrom || undefined} onChange={event => { setDateTo(event.target.value); setPage(1); }} /></label></div>
        <label className="admin-filter"><span>{bn ? "সাজানো" : "Sort"}</span><select value={sortDirection} onChange={event => setSortDirection(event.target.value as "asc" | "desc")}><option value="asc">A–Z</option><option value="desc">Z–A</option></select></label>
        {selected.size ? <div className="admin-bulk-actions"><button className="admin-row-button admin-row-button--danger" type="button" onClick={() => { setBulkArchived(true); setNote(""); }}>Archive ({selected.size})</button><button className="admin-row-button admin-row-button--approve" type="button" onClick={() => { setBulkArchived(false); setNote(""); }}>Restore ({selected.size})</button></div> : null}
      </div>
      <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th className="admin-checkbox-cell"><input type="checkbox" aria-label={bn ? "সব rule নির্বাচন" : "Select all rules"} checked={allSelected} onChange={event => setSelected(event.target.checked ? new Set(visibleRows.map(row => row.id)) : new Set())} /></th><th>ID</th><th>{bn ? "Rule" : "Rule"}</th><th>{bn ? "মান" : "Value"}</th><th>{bn ? "অবস্থা" : "Status"}</th><th>{bn ? "আপডেট" : "Updated"}</th><th><span className="sr-only">{bn ? "অ্যাকশন" : "Actions"}</span></th></tr></thead>
        <tbody>{visibleRows.map(row => <tr key={row.id}><td className="admin-checkbox-cell"><input type="checkbox" aria-label={`Select rule ${row.id}`} checked={selected.has(row.id)} onChange={event => setSelected(current => { const next = new Set(current); if (event.target.checked) next.add(row.id); else next.delete(row.id); return next; })} /></td><td>#{row.id}</td><td><strong>{rowSummary(row)}</strong></td><td>{rowValue(row, intlLocale)}</td><td><span className={`admin-status admin-status--${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "ACTIVE" : "ARCHIVED"}</span></td><td>{formatDateTime(row.updated_at, intlLocale)}</td><td className="admin-actions-cell"><div className="admin-inline-actions"><button className="admin-row-button" type="button" onClick={() => openEdit(row)}>Edit</button><button className={row.is_active ? "admin-row-button admin-row-button--danger" : "admin-row-button admin-row-button--approve"} type="button" onClick={() => { setArchiveTarget({ row, archived: row.is_active }); setNote(""); }}>{row.is_active ? "Archive" : "Restore"}</button></div></td></tr>)}</tbody>
      </table></div>
      {!visibleRows.length ? <div className="admin-empty"><strong>{bn ? "কোনো rule পাওয়া যায়নি" : "No rules found"}</strong><span>{bn ? "Filter পরিবর্তন করুন বা নতুন rule যোগ করুন।" : "Change the filters or add a new rule."}</span></div> : null}
      <footer className="admin-pagination"><span>{filtered.length} {bn ? "রেকর্ড" : "records"}</span><div><button type="button" disabled={page <= 1} onClick={() => setPage(current => Math.max(1, current - 1))}>{bn ? "আগের" : "Previous"}</button><span>{bn ? "পৃষ্ঠা" : "Page"} {Math.min(page, pages)} / {pages}</span><button type="button" disabled={page >= pages} onClick={() => setPage(current => current + 1)}>{bn ? "পরের" : "Next"}</button></div><label><span>{bn ? "প্রতি পৃষ্ঠা" : "Per page"}</span><select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); }}><option value="10">10</option><option value="20">20</option><option value="50">50</option></select></label></footer>
    </section>

    <AdminModal open={editing !== null} onClose={() => !saving && setEditing(null)} title={editing === "new" ? (bn ? "রুল যোগ করুন" : "Add rule") : (bn ? "রুল সম্পাদনা" : "Edit rule")} description={bn ? "এই মানগুলো live price ও ETA calculation-এ ব্যবহৃত হবে; প্রতিটি পরিবর্তন audit করা হয়।" : "These values feed live price and ETA calculations; every change is audited."}>
      <form className="admin-modal__form" onSubmit={save}>
        {type === "currencies" ? <><label><span>{bn ? "মুদ্রা কোড" : "Currency code"}</span><input minLength={3} maxLength={10} pattern="[A-Za-z]+" required value={fields.currency || ""} onChange={event => setField("currency", event.target.value)} /></label><label><span>{bn ? "BDT rate" : "Rate to BDT"}</span><input type="number" min=".0001" step=".0001" required value={fields.rate_to_bdt || ""} onChange={event => setField("rate_to_bdt", event.target.value)} /></label></> : null}
        {type === "service-fees" ? <><label><span>{bn ? "মোড" : "Mode"}</span><select value={fields.mode || "LOCAL"} onChange={event => setField("mode", event.target.value)}><option value="LOCAL">LOCAL</option><option value="BULK">BULK</option></select></label><label><span>{bn ? "স্থির fee (BDT)" : "Fixed fee (BDT)"}</span><input type="number" min="0" step=".01" required value={fields.fee_bdt || "0"} onChange={event => setField("fee_bdt", event.target.value)} /></label><label><span>{bn ? "শতাংশ" : "Percent"}</span><input type="number" min="0" max="100" step=".01" required value={fields.percent || "0"} onChange={event => setField("percent", event.target.value)} /></label></> : null}
        {type === "shipping-rates" || type === "eta-rules" || type === "duty-rules" ? <label><span>{bn ? "দেশ" : "Country"}</span><select required value={fields.country_id || ""} onChange={event => setField("country_id", event.target.value)}>{countries.map(country => <option key={country.id} value={country.id}>{country.code} · {country.name}</option>)}</select></label> : null}
        {type === "shipping-rates" ? <><label><span>{bn ? "পদ্ধতি" : "Method"}</span><select value={fields.method || "AIR"} onChange={event => setField("method", event.target.value)}><option value="AIR">AIR</option><option value="SEA">SEA</option></select></label><label><span>Min kg</span><input type="number" min="0" step=".001" required value={fields.min_kg || "0"} onChange={event => setField("min_kg", event.target.value)} /></label><label><span>Max kg</span><input type="number" min=".001" step=".001" required value={fields.max_kg || ""} onChange={event => setField("max_kg", event.target.value)} /></label><label><span>{bn ? "খরচ (BDT)" : "Cost (BDT)"}</span><input type="number" min="0" step=".01" required value={fields.cost_bdt || "0"} onChange={event => setField("cost_bdt", event.target.value)} /></label></> : null}
        {type === "eta-rules" ? <><label><span>{bn ? "মোড" : "Mode"}</span><select value={fields.mode || "LOCAL"} onChange={event => setField("mode", event.target.value)}><option value="LOCAL">LOCAL</option><option value="BULK">BULK</option></select></label><label><span>{bn ? "ডেলিভারি" : "Delivery"}</span><select value={fields.delivery_type || "DOOR"} onChange={event => setField("delivery_type", event.target.value)}><option value="DOOR">DOOR</option><option value="PICKUP">PICKUP</option></select></label><label><span>{bn ? "সর্বনিম্ন দিন" : "Minimum days"}</span><input type="number" min="0" max="365" required value={fields.min_days || "0"} onChange={event => setField("min_days", event.target.value)} /></label><label><span>{bn ? "সর্বোচ্চ দিন" : "Maximum days"}</span><input type="number" min="0" max="365" required value={fields.max_days || "0"} onChange={event => setField("max_days", event.target.value)} /></label></> : null}
        {type === "duty-rules" ? <><label><span>{bn ? "ক্যাটাগরি (ঐচ্ছিক)" : "Category (optional)"}</span><select value={fields.category_id || ""} onChange={event => setField("category_id", event.target.value)}><option value="">{bn ? "সব ক্যাটাগরি" : "All categories"}</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label><span>{bn ? "শতাংশ" : "Percent"}</span><input type="number" min="0" max="100" step=".01" required value={fields.percent || "0"} onChange={event => setField("percent", event.target.value)} /></label><label><span>{bn ? "স্থির duty (BDT)" : "Fixed duty (BDT)"}</span><input type="number" min="0" step=".01" required value={fields.fixed_bdt || "0"} onChange={event => setField("fixed_bdt", event.target.value)} /></label><label><span>{bn ? "কার্যকর শুরু (Dhaka)" : "Effective from (Dhaka)"}</span><input type="datetime-local" value={fields.effective_from || ""} onChange={event => setField("effective_from", event.target.value)} /></label><label><span>{bn ? "কার্যকর শেষ (Dhaka)" : "Effective to (Dhaka)"}</span><input type="datetime-local" value={fields.effective_to || ""} onChange={event => setField("effective_to", event.target.value)} /></label></> : null}
        <label><span>{bn ? "আবশ্যিক audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} rows={3} required value={note} onChange={event => setNote(event.target.value)} /></label>
        {error ? <div className="admin-alert admin-alert--error">{error}</div> : null}
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setEditing(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || note.trim().length < 3}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div>
      </form>
    </AdminModal>

    <AdminModal open={archiveTarget !== null} onClose={() => !saving && setArchiveTarget(null)} title={archiveTarget?.archived ? (bn ? "রুল archive করবেন?" : "Archive rule?") : (bn ? "রুল restore করবেন?" : "Restore rule?")} description={bn ? "এই পরিবর্তন price/ETA calculation-এ প্রভাব ফেলতে পারে এবং audit log-এ থাকবে।" : "This may affect price or ETA calculations and will be recorded in the audit log."}><form className="admin-modal__form" onSubmit={archiveOne}><label><span>{bn ? "আবশ্যিক audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} rows={3} required value={note} onChange={event => setNote(event.target.value)} /></label><div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setArchiveTarget(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className={archiveTarget?.archived ? "admin-button admin-button--danger" : "admin-button admin-button--primary"} disabled={saving || note.trim().length < 3}>{bn ? "নিশ্চিত করুন" : "Confirm"}</button></div></form></AdminModal>

    <AdminModal open={bulkArchived !== null} onClose={() => !saving && setBulkArchived(null)} title={bulkArchived ? (bn ? "নির্বাচিত রুল archive করবেন?" : "Archive selected rules?") : (bn ? "নির্বাচিত রুল restore করবেন?" : "Restore selected rules?")} description={bn ? `${selected.size}টি real API operation চালানো হবে; প্রতিটি পরিবর্তনের আলাদা audit record থাকবে।` : `${selected.size} real API operations will run, each with its own audit record.`}><form className="admin-modal__form" onSubmit={archiveMany}><label><span>{bn ? "আবশ্যিক audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} rows={3} required value={note} onChange={event => setNote(event.target.value)} /></label><div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setBulkArchived(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className={bulkArchived ? "admin-button admin-button--danger" : "admin-button admin-button--primary"} disabled={saving || note.trim().length < 3}>{bn ? "নিশ্চিত করুন" : "Confirm"}</button></div></form></AdminModal>
    {toast ? <div className={`admin-toast admin-toast--${toast.kind}`} role="status">{toast.message}</div> : null}
  </div>;
}
