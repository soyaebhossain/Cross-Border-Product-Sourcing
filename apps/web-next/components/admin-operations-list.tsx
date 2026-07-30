"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Paged } from "../lib/customer-api";
import { useLocale } from "../lib/locale-context";

export type AdminOperationsQuery = {
  q?: string;
  status?: string;
  channel?: string;
  limit: number;
  offset: number;
};

export type AdminOperationsColumn<T> = {
  key: string;
  label: string;
  cell: (row: T) => React.ReactNode;
  exportValue?: (row: T) => string | number | null | undefined;
  sortValue?: (row: T) => string | number | null | undefined;
  numeric?: boolean;
};

type OperationsFilter = {
  key: "status" | "channel";
  label: string;
  options: Array<{ value: string; label: string }>;
};

type Props<T extends { id: number }> = {
  resourceName: string;
  eyebrow: string;
  title: string;
  description: string;
  columns: AdminOperationsColumn<T>[];
  load: (query: AdminOperationsQuery) => Promise<Paged<T>>;
  searchPlaceholder?: string;
  localSearch?: (row: T, query: string) => boolean;
  filters?: OperationsFilter[];
  detailHref: (row: T) => string;
  actions?: (
    row: T,
    reload: () => Promise<void>,
    notify: (message: string, kind?: "success" | "error") => void,
  ) => React.ReactNode;
  headerAction?: React.ReactNode | ((
    reload: () => Promise<void>,
    notify: (message: string, kind?: "success" | "error") => void,
  ) => React.ReactNode);
};

function escapeCsv(value: unknown) {
  return `"${String(value ?? "").replaceAll("\"", "\"\"")}"`;
}

export function AdminOperationsList<T extends { id: number }>({
  resourceName,
  eyebrow,
  title,
  description,
  columns,
  load,
  searchPlaceholder,
  localSearch,
  filters = [],
  detailHref,
  actions,
  headerAction,
}: Props<T>) {
  const [data, setData] = useState<Paged<T>>({ items: [], total: 0, limit: 25, offset: 0 });
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sort, setSort] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ message: string; kind: "success" | "error" } | null>(null);
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const notify = useCallback((message: string, kind: "success" | "error" = "success") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), 3600);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await load({
        q: localSearch ? undefined : query || undefined,
        status: filterValues.status || undefined,
        channel: filterValues.channel || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setData(result);
      if (result.total > 0 && result.offset >= result.total && page > 1) {
        setPage(Math.max(1, Math.ceil(result.total / pageSize)));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "রেকর্ড লোড করা যায়নি।" : "Records could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, filterValues.channel, filterValues.status, load, localSearch, page, pageSize, query]);

  useEffect(() => { void reload(); }, [reload]);

  const rows = useMemo(() => {
    const filtered = localSearch && query
      ? data.items.filter(row => localSearch(row, query))
      : data.items;
    if (!sort) return filtered;
    const column = columns.find(item => item.key === sort.key);
    if (!column?.sortValue) return filtered;
    return [...filtered].sort((left, right) => {
      const a = column.sortValue?.(left);
      const b = column.sortValue?.(right);
      const comparison = typeof a === "number" && typeof b === "number"
        ? a - b
        : String(a ?? "").localeCompare(String(b ?? ""), intlLocale, { numeric: true, sensitivity: "base" });
      return sort.direction === "asc" ? comparison : -comparison;
    });
  }, [columns, data.items, intlLocale, localSearch, query, sort]);

  const pages = Math.max(1, Math.ceil(data.total / pageSize));
  const toggleSort = (column: AdminOperationsColumn<T>) => {
    if (!column.sortValue) return;
    setSort(current => current?.key === column.key
      ? { key: column.key, direction: current.direction === "asc" ? "desc" : "asc" }
      : { key: column.key, direction: "asc" });
  };

  const exportRows = () => {
    if (!rows.length) return;
    const csv = [
      columns.map(column => escapeCsv(column.label)).join(","),
      ...rows.map(row => columns.map(column => escapeCsv(column.exportValue?.(row))).join(",")),
    ].join("\r\n");
    const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sourceai-${resourceName}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    notify(bn ? "বর্তমান পৃষ্ঠার CSV প্রস্তুত হয়েছে।" : "The current page CSV is ready.");
  };

  const clearFilters = () => {
    setDraftQuery("");
    setQuery("");
    setFilterValues({});
    setPage(1);
  };

  return <div className="admin-page">
    <header className="admin-page-header">
      <div><p className="admin-eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>
      <div className="admin-toolbar">
        {typeof headerAction === "function" ? headerAction(reload, notify) : headerAction}
        <button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()} disabled={!rows.length}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button>
        <button className="admin-button admin-button--secondary" type="button" onClick={exportRows} disabled={!rows.length}>{bn ? "CSV এক্সপোর্ট" : "Export CSV"}</button>
        <button className="admin-button admin-button--secondary" type="button" onClick={() => void reload()} disabled={loading}>{loading ? (bn ? "লোড হচ্ছে…" : "Loading…") : (bn ? "রিফ্রেশ" : "Refresh")}</button>
      </div>
    </header>

    <section className="admin-card admin-list-card">
      <form className="admin-list-toolbar" onSubmit={event => { event.preventDefault(); setPage(1); setQuery(draftQuery.trim()); }}>
        {searchPlaceholder ? <label className="admin-search">
          <span className="sr-only">{localSearch ? (bn ? "বর্তমান পৃষ্ঠা ফিল্টার করুন" : "Filter current page") : (bn ? "খুঁজুন" : "Search")}</span>
          <svg viewBox="0 0 24 24" aria-hidden><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>
          <input value={draftQuery} onChange={event => setDraftQuery(event.target.value)} placeholder={searchPlaceholder} />
          <button type="submit">{localSearch ? (bn ? "ফিল্টার" : "Filter") : (bn ? "খুঁজুন" : "Search")}</button>
        </label> : null}
        {filters.map(filter => <label className="admin-filter" key={filter.key}>
          <span>{filter.label}</span>
          <select value={filterValues[filter.key] || ""} onChange={event => { setPage(1); setFilterValues(current => ({ ...current, [filter.key]: event.target.value })); }}>
            <option value="">{bn ? "সব" : "All"}</option>
            {filter.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>)}
        {(query || Object.values(filterValues).some(Boolean)) ? <button className="admin-clear" type="button" onClick={clearFilters}>{bn ? "ফিল্টার মুছুন" : "Clear filters"}</button> : null}
      </form>

      {localSearch && query ? <div className="admin-ops-note" role="status">{bn ? `লোড করা ${data.items.length}টি রেকর্ডের মধ্যে ${rows.length}টি মিলেছে।` : `${rows.length} of ${data.items.length} loaded records match this page filter.`}</div> : null}
      {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Unable to load"}</strong><span>{error}</span><button type="button" onClick={() => void reload()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}
      {loading && !data.items.length ? <div className="admin-loading" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "রেকর্ড লোড হচ্ছে…" : "Loading records…"}</div> : null}

      {!error && (!loading || data.items.length) ? <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr>{columns.map(column => <th scope="col" key={column.key} className={column.numeric ? "admin-cell--numeric" : undefined}>{column.sortValue ? <button className="admin-sort" type="button" onClick={() => toggleSort(column)}>{column.label}<span aria-hidden>{sort?.key === column.key ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</span></button> : column.label}</th>)}<th scope="col"><span className="sr-only">{bn ? "অ্যাকশন" : "Actions"}</span></th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.id}>{columns.map(column => <td key={column.key} className={column.numeric ? "admin-cell--numeric" : undefined}>{column.cell(row)}</td>)}<td className="admin-actions-cell"><div className="admin-inline-actions"><Link className="admin-row-button" href={detailHref(row) as Route}>{bn ? "বিস্তারিত" : "Details"}</Link>{actions?.(row, reload, notify)}</div></td></tr>)}</tbody>
      </table></div> : null}
      {!loading && !error && !rows.length ? <div className="admin-empty"><strong>{bn ? "কোনো রেকর্ড পাওয়া যায়নি" : "No records found"}</strong><span>{bn ? "সার্চ বা ফিল্টার পরিবর্তন করে দেখুন।" : "Try changing the search or filters."}</span></div> : null}

      <footer className="admin-pagination">
        <span>{new Intl.NumberFormat(intlLocale).format(data.total)} {bn ? "রেকর্ড" : "records"}</span>
        <div>
          <button type="button" disabled={page <= 1 || loading} onClick={() => setPage(current => Math.max(1, current - 1))}>{bn ? "আগের" : "Previous"}</button>
          <span>{bn ? "পৃষ্ঠা" : "Page"} {new Intl.NumberFormat(intlLocale).format(page)} / {new Intl.NumberFormat(intlLocale).format(pages)}</span>
          <button type="button" disabled={page >= pages || loading} onClick={() => setPage(current => current + 1)}>{bn ? "পরের" : "Next"}</button>
        </div>
        <label><span>{bn ? "প্রতি পৃষ্ঠা" : "Per page"}</span><select value={pageSize} onChange={event => { setPage(1); setPageSize(Number(event.target.value)); }}><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label>
      </footer>
    </section>
    {toast ? <div className={`admin-toast admin-toast--${toast.kind}`} role="status">{toast.message}</div> : null}
  </div>;
}
