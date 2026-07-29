"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { getAdminList, type AdminListResponse } from "../lib/api";
import { useLocale } from "../lib/locale-context";
import { useAdminAccess } from "../lib/use-admin-access";
import { AdminModal } from "./admin-modal";

export type AdminResource = "orders" | "payments" | "quotes" | "products" | "categories" | "variants" | "suppliers" | "offers" | "users" | "audit";
export type AdminFilter = {
  key: string;
  label: string;
  options: Array<{ value: string; label: string }>;
  defaultValue?: string;
};
export type AdminColumn<T> = {
  key: string;
  label: string;
  cell: (row: T) => React.ReactNode;
  exportValue?: (row: T) => string | number | null | undefined;
  sortValue?: (row: T) => string | number | null | undefined;
  numeric?: boolean;
};

type Props<T extends { id?: number | string; order_id?: number }> = {
  resource: AdminResource;
  eyebrow: string;
  title: string;
  description: string;
  searchPlaceholder: string;
  columns: AdminColumn<T>[];
  filters?: AdminFilter[];
  getRowId?: (row: T) => string;
  actions?: (row: T, reload: () => Promise<void>, notify: (message: string, kind?: "success" | "error") => void) => React.ReactNode;
  headerAction?: React.ReactNode;
  detailHref?: (row: T) => string;
  showDateRange?: boolean;
  bulkActions?: Array<{
    label: string;
    kind?: "default" | "danger";
    run: (ids: number[], note: string) => Promise<void>;
  }>;
};

function escapeCsv(value: unknown) {
  const text = String(value ?? "");
  return `"${text.replaceAll("\"", "\"\"")}"`;
}

export function AdminDataPage<T extends { id?: number | string; order_id?: number }>({
  resource,
  eyebrow,
  title,
  description,
  searchPlaceholder,
  columns,
  filters = [],
  getRowId,
  actions,
  headerAction,
  detailHref,
  showDateRange = false,
  bulkActions = [],
}: Props<T>) {
  const [data, setData] = useState<AdminListResponse<T>>({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  const [qDraft, setQDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filterValues, setFilterValues] = useState<Record<string, string>>(() => Object.fromEntries(filters.filter(filter => filter.defaultValue).map(filter => [filter.key, filter.defaultValue as string])));
  const [sort, setSort] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ message: string; kind: "success" | "error" } | null>(null);
  const [pendingBulk, setPendingBulk] = useState<number | null>(null);
  const [bulkNote, setBulkNote] = useState("");
  const [bulkSaving, setBulkSaving] = useState(false);
  const { locale, intlLocale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";
  const adminManagedResource = ["products", "categories", "variants", "suppliers", "offers"].includes(resource);
  const mutationAllowed = !adminManagedResource || isAdmin;
  const availableBulkActions = mutationAllowed ? bulkActions : [];

  const notify = useCallback((message: string, kind: "success" | "error" = "success") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), 3600);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getAdminList<T>(resource, {
        q,
        page,
        page_size: pageSize,
        date_from: dateFrom,
        date_to: dateTo,
        ...filterValues,
      });
      setData({
        items: Array.isArray(result) ? result : result.items || [],
        total: Array.isArray(result) ? result.length : result.total || 0,
        page: Array.isArray(result) ? 1 : result.page || page,
        page_size: Array.isArray(result) ? result.length || pageSize : result.page_size || pageSize,
        pages: Array.isArray(result) ? 1 : result.pages || 0,
      });
      setSelected(new Set());
    } catch {
      setError(bn ? "ডেটা লোড করা যায়নি। আপনার অ্যাক্সেস ও API সংযোগ যাচাই করুন।" : "Data could not be loaded. Check your access and API connection.");
    } finally {
      setLoading(false);
    }
  }, [resource, q, page, pageSize, dateFrom, dateTo, filterValues, bn]);

  useEffect(() => { reload(); }, [reload]);
  useEffect(() => {
    const initialQuery = new URLSearchParams(window.location.search).get("q") || "";
    if (initialQuery) {
      setQDraft(initialQuery);
      setQ(initialQuery);
    }
  }, []);

  const rowId = useCallback((row: T) => getRowId ? getRowId(row) : String(row.id ?? row.order_id), [getRowId]);
  const rows = useMemo(() => {
    if (!sort) return data.items;
    const column = columns.find(item => item.key === sort.key);
    if (!column?.sortValue) return data.items;
    return [...data.items].sort((left, right) => {
      const a = column.sortValue?.(left);
      const b = column.sortValue?.(right);
      const result = typeof a === "number" && typeof b === "number"
        ? a - b
        : String(a ?? "").localeCompare(String(b ?? ""), intlLocale, { numeric: true, sensitivity: "base" });
      return sort.direction === "asc" ? result : -result;
    });
  }, [data.items, sort, columns, intlLocale]);

  const toggleSort = (column: AdminColumn<T>) => {
    if (!column.sortValue) return;
    setSort(current => current?.key === column.key
      ? { key: column.key, direction: current.direction === "asc" ? "desc" : "asc" }
      : { key: column.key, direction: "asc" });
  };

  const exportRows = () => {
    const exportItems = selected.size ? rows.filter(row => selected.has(rowId(row))) : rows;
    if (!exportItems.length) return;
    const csv = [
      columns.map(column => escapeCsv(column.label)).join(","),
      ...exportItems.map(row => columns.map(column => escapeCsv(column.exportValue ? column.exportValue(row) : "")).join(",")),
    ].join("\r\n");
    const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sourceai-${resource}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    notify(bn ? "CSV প্রস্তুত হয়েছে।" : "CSV export is ready.");
  };

  const printRows = () => {
    document.documentElement.dataset.printSelection = selected.size ? "selected" : "all";
    window.requestAnimationFrame(() => {
      window.print();
      window.setTimeout(() => { delete document.documentElement.dataset.printSelection; }, 100);
    });
  };

  const allSelected = rows.length > 0 && rows.every(row => selected.has(rowId(row)));
  const runBulkAction = async (event: React.FormEvent) => {
    event.preventDefault();
    if (pendingBulk === null || !availableBulkActions[pendingBulk]) return;
    setBulkSaving(true);
    try {
      const ids = [...selected].map(Number).filter(Number.isFinite);
      await availableBulkActions[pendingBulk].run(ids, bulkNote);
      notify(bn ? "Bulk action audit log-সহ সম্পন্ন হয়েছে।" : "Bulk action completed with an audit record.");
      setPendingBulk(null);
      setBulkNote("");
      await reload();
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : (bn ? "Bulk action ব্যর্থ হয়েছে।" : "Bulk action failed."), "error");
    } finally {
      setBulkSaving(false);
    }
  };

  return (
    <div className="admin-page">
      <header className="admin-page-header">
        <div><p className="admin-eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>
        <div className="admin-toolbar">{mutationAllowed ? headerAction : <span className="admin-read-only">{bn ? "Operator · শুধু দেখুন" : "Operator · read only"}</span>}<button className="admin-button admin-button--secondary" type="button" onClick={printRows} disabled={!rows.length}>{selected.size ? `${bn ? "নির্বাচিত PDF" : "Print selected"} (${selected.size})` : (bn ? "প্রিন্ট / PDF" : "Print / PDF")}</button><button className="admin-button admin-button--secondary" type="button" onClick={exportRows} disabled={!rows.length}>{selected.size ? `${bn ? "নির্বাচিত CSV" : "Export selected"} (${selected.size})` : (bn ? "CSV এক্সপোর্ট" : "Export CSV")}</button><button className="admin-button admin-button--secondary" type="button" onClick={reload} disabled={loading}>{loading ? (bn ? "লোড হচ্ছে…" : "Loading…") : (bn ? "রিফ্রেশ" : "Refresh")}</button></div>
      </header>

      <section className="admin-card admin-list-card">
        <form className="admin-list-toolbar" onSubmit={event => { event.preventDefault(); setPage(1); setQ(qDraft.trim()); }}>
          <label className="admin-search"><span className="sr-only">{bn ? "খুঁজুন" : "Search"}</span><svg viewBox="0 0 24 24" aria-hidden><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg><input value={qDraft} onChange={event => setQDraft(event.target.value)} placeholder={searchPlaceholder} /><button type="submit">{bn ? "খুঁজুন" : "Search"}</button></label>
          {showDateRange ? <div className="admin-date-range" role="group" aria-label={bn ? "তারিখ সীমা" : "Date range"}>
            <label className="admin-filter"><span>{bn ? "শুরু" : "From"}</span><input type="date" value={dateFrom} max={dateTo || undefined} onChange={event => { setPage(1); setDateFrom(event.target.value); }} /></label>
            <label className="admin-filter"><span>{bn ? "শেষ" : "To"}</span><input type="date" value={dateTo} min={dateFrom || undefined} onChange={event => { setPage(1); setDateTo(event.target.value); }} /></label>
          </div> : null}
          {filters.map(filter => <label className="admin-filter" key={filter.key}><span>{filter.label}</span><select value={filterValues[filter.key] || ""} onChange={event => { setPage(1); setFilterValues(current => ({ ...current, [filter.key]: event.target.value })); }}><option value="">{bn ? "সব" : "All"}</option>{filter.options.map(option => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>)}
          {(q || dateFrom || dateTo || Object.values(filterValues).some(Boolean)) ? <button type="button" className="admin-clear" onClick={() => { setQ(""); setQDraft(""); setDateFrom(""); setDateTo(""); setFilterValues({}); setPage(1); }}>{bn ? "ফিল্টার মুছুন" : "Clear filters"}</button> : null}
          {selected.size && availableBulkActions.length ? <div className="admin-bulk-actions">{availableBulkActions.map((action, index) => <button className={action.kind === "danger" ? "admin-row-button admin-row-button--danger" : "admin-row-button"} type="button" key={action.label} onClick={() => setPendingBulk(index)}>{action.label} ({selected.size})</button>)}</div> : null}
        </form>

        {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Unable to load"}</strong><span>{error}</span><button type="button" onClick={reload}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}
        {loading && !data.items.length ? <div className="admin-loading" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "রেকর্ড লোড হচ্ছে…" : "Loading records…"}</div> : null}

        {!error && (!loading || data.items.length > 0) ? <div className="admin-table-wrap"><table className="admin-data-table">
          <thead><tr><th className="admin-checkbox-cell" scope="col"><input type="checkbox" aria-label={bn ? "সব সারি নির্বাচন" : "Select all rows"} checked={allSelected} onChange={event => setSelected(event.target.checked ? new Set(rows.map(rowId)) : new Set())} /></th>{columns.map(column => <th scope="col" key={column.key} className={column.numeric ? "admin-cell--numeric" : undefined}>{column.sortValue ? <button className="admin-sort" type="button" onClick={() => toggleSort(column)}>{column.label}<span aria-hidden>{sort?.key === column.key ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</span></button> : column.label}</th>)}{(mutationAllowed && actions) || detailHref ? <th scope="col"><span className="sr-only">{bn ? "অ্যাকশন" : "Actions"}</span></th> : null}</tr></thead>
          <tbody>{rows.map(row => {
            const id = rowId(row);
            return <tr key={id} className={selected.size && !selected.has(id) ? "admin-row--print-hidden" : undefined}><td className="admin-checkbox-cell"><input type="checkbox" aria-label={`${bn ? "সারি নির্বাচন" : "Select row"} ${id}`} checked={selected.has(id)} onChange={event => setSelected(current => { const next = new Set(current); if (event.target.checked) next.add(id); else next.delete(id); return next; })} /></td>{columns.map(column => <td key={column.key} className={column.numeric ? "admin-cell--numeric" : undefined}>{column.cell(row)}</td>)}{(mutationAllowed && actions) || detailHref ? <td className="admin-actions-cell"><div className="admin-inline-actions">{detailHref ? <Link className="admin-row-button" href={detailHref(row) as Route}>{bn ? "বিস্তারিত" : "Details"}</Link> : null}{mutationAllowed && actions ? actions(row, reload, notify) : null}</div></td> : null}</tr>;
          })}</tbody>
        </table></div> : null}
        {!loading && !error && !rows.length ? <div className="admin-empty"><strong>{bn ? "কোনো রেকর্ড পাওয়া যায়নি" : "No records found"}</strong><span>{bn ? "সার্চ বা ফিল্টার পরিবর্তন করে দেখুন।" : "Try changing the search or filters."}</span></div> : null}

        <footer className="admin-pagination">
          <span>{new Intl.NumberFormat(intlLocale).format(data.total)} {bn ? "রেকর্ড" : "records"}</span>
          <div><button type="button" disabled={page <= 1 || loading} onClick={() => setPage(current => Math.max(1, current - 1))}>{bn ? "আগের" : "Previous"}</button><span>{bn ? "পৃষ্ঠা" : "Page"} {new Intl.NumberFormat(intlLocale).format(data.page || page)} / {new Intl.NumberFormat(intlLocale).format(Math.max(data.pages || 1, 1))}</span><button type="button" disabled={page >= Math.max(data.pages, 1) || loading} onClick={() => setPage(current => current + 1)}>{bn ? "পরের" : "Next"}</button></div>
          <label><span>{bn ? "প্রতি পৃষ্ঠা" : "Per page"}</span><select value={pageSize} onChange={event => { setPage(1); setPageSize(Number(event.target.value)); }}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></label>
        </footer>
      </section>
      <AdminModal open={pendingBulk !== null} onClose={() => !bulkSaving && setPendingBulk(null)} title={pendingBulk === null ? "" : availableBulkActions[pendingBulk]?.label || ""} description={bn ? `${selected.size}টি selected record পরিবর্তন হবে। প্রতিটি পরিবর্তন audit করা হবে।` : `${selected.size} selected records will change. Every change is audited.`}>
        <form className="admin-modal__form" onSubmit={runBulkAction}><label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} required rows={3} value={bulkNote} onChange={event => setBulkNote(event.target.value)} /></label><div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={bulkSaving} onClick={() => setPendingBulk(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className={pendingBulk !== null && availableBulkActions[pendingBulk]?.kind === "danger" ? "admin-button admin-button--danger" : "admin-button admin-button--primary"} disabled={bulkSaving || bulkNote.trim().length < 3}>{bulkSaving ? (bn ? "চলছে…" : "Working…") : (bn ? "নিশ্চিত করুন" : "Confirm")}</button></div></form>
      </AdminModal>
      {toast ? <div className={`admin-toast admin-toast--${toast.kind}`} role="status">{toast.message}</div> : null}
    </div>
  );
}
