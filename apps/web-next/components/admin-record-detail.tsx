"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useState } from "react";
import { AdminArchiveAction } from "./admin-archive-action";
import { useLocale } from "../lib/locale-context";
import { useAdminAccess } from "../lib/use-admin-access";

type Entity = "categories" | "products" | "variants" | "suppliers" | "offers";

export type DetailSection = {
  title: string;
  description?: string;
  values: Array<{ label: string; value: React.ReactNode }>;
};

export function AdminRecordDetail<T extends { id: number; is_active: boolean }>({
  entity,
  id,
  backHref,
  backLabel,
  eyebrow,
  load,
  heading,
  subheading,
  sections,
}: {
  entity: Entity;
  id: string;
  backHref: Route;
  backLabel: string;
  eyebrow: string;
  load: (id: string) => Promise<T>;
  heading: (record: T) => string;
  subheading?: (record: T) => string;
  sections: (record: T) => DetailSection[];
}) {
  const [record, setRecord] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ message: string; kind: "success" | "error" } | null>(null);
  const { locale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRecord(await load(id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "রেকর্ডটি লোড করা যায়নি।" : "The record could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, id, load]);

  useEffect(() => { void reload(); }, [reload]);

  const notify = useCallback((message: string, kind: "success" | "error" = "success") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), 3600);
  }, []);

  if (loading && !record) {
    return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "রেকর্ড লোড হচ্ছে…" : "Loading record…"}</div>;
  }

  if (!record) {
    return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "রেকর্ড পাওয়া যায়নি" : "Record unavailable"}</strong><span>{error}</span><button type="button" onClick={() => void reload()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div></div>;
  }

  return <div className="admin-page">
    <header className="admin-page-header">
      <div>
        <Link className="account-back-link" href={backHref}>← {backLabel}</Link>
        <p className="admin-eyebrow">{eyebrow}</p>
        <h1>{heading(record)}</h1>
        <p>{subheading?.(record) || `Record #${record.id}`}</p>
      </div>
      <div className="admin-toolbar">
        <button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button>
        {isAdmin ? <AdminArchiveAction entity={entity} id={record.id} isActive={record.is_active} reload={reload} notify={notify} /> : <span className="admin-read-only">{bn ? "Operator · শুধু দেখুন" : "Operator · read only"}</span>}
      </div>
    </header>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "রিফ্রেশ ব্যর্থ" : "Refresh failed"}</strong><span>{error}</span><button type="button" onClick={() => void reload()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}

    <div className="admin-detail-grid">
      {sections(record).map(section => <section className="admin-card" key={section.title}>
        <div className="admin-card__header"><div><h2>{section.title}</h2>{section.description ? <p>{section.description}</p> : null}</div></div>
        <dl className="account-definition-list">
          {section.values.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value ?? "—"}</dd></div>)}
        </dl>
      </section>)}
    </div>

    {toast ? <div className={`admin-toast admin-toast--${toast.kind}`} role="status">{toast.message}</div> : null}
  </div>;
}
