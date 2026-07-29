"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getAdminRoles, type AdminRoleContract } from "../../../lib/admin-api";
import { useLocale } from "../../../lib/locale-context";

const labels: Record<string, string> = {
  own_profile: "Own profile and address book",
  own_saved_quotes: "Own saved quotes",
  own_orders: "Own orders and invoices",
  own_payments: "Own payments and retries",
  admin_overview: "Operational overview and analytics",
  orders_operate: "Operate orders and shipping",
  payments_decide: "Decide payment proofs",
  refunds_operate: "Operate refunds and reversals",
  quotes_read: "Read customer saved quotes",
  catalog_read: "Read products and categories",
  supplier_read: "Read suppliers and offers",
  research_analytics: "Research analytics and CSV export",
  catalog_manage: "Manage catalog and suppliers",
  settings_manage: "Manage currency, shipping, ETA and duty",
  users_manage: "Manage users and role assignments",
  roles_read: "Read role policy",
  audit_read: "Read complete audit logs",
};

function Permission({ allowed }: { allowed: boolean }) {
  return <span className={allowed ? "admin-permission admin-permission--yes" : "admin-permission admin-permission--no"} aria-label={allowed ? "Allowed" : "Not allowed"}>{allowed ? "✓" : "—"}</span>;
}

export default function AdminRolesPage() {
  const [contract, setContract] = useState<AdminRoleContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setContract(await getAdminRoles()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : (bn ? "Role policy লোড করা যায়নি।" : "Role policy could not be loaded.")); }
    finally { setLoading(false); }
  }, [bn]);
  useEffect(() => { void load(); }, [load]);

  const roles = useMemo(() => {
    const items = contract?.items || [];
    const operator = items.find(item => item.role === "operator")?.capabilities || [];
    return items.map(item => ({
      ...item,
      capabilities: item.capabilities.includes("all_operator_capabilities")
        ? [...new Set([...operator, ...item.capabilities.filter(capability => capability !== "all_operator_capabilities")])]
        : item.capabilities,
    }));
  }, [contract]);
  const capabilities = useMemo(() => [...new Set(roles.flatMap(role => role.capabilities))], [roles]);

  return <div className="admin-page">
    <header className="admin-page-header">
      <div><p className="admin-eyebrow">{bn ? "Server-enforced RBAC" : "Server-enforced RBAC"}</p><h1>{bn ? "রোল ও অনুমতি" : "Roles and permissions"}</h1><p>{contract?.policy || (bn ? "Backend role contract থেকে capability দেখানো হচ্ছে।" : "Capabilities are read from the backend role contract.")}</p></div>
      <div className="admin-toolbar"><Link className="admin-button admin-button--primary" href="/admin/users">{bn ? "ইউজার পরিচালনা" : "Manage users"}</Link><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()} disabled={!contract}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></div>
    </header>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "Policy পাওয়া যায়নি" : "Policy unavailable"}</strong><span>{error}</span><button type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}
    {loading && !contract ? <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "Role contract লোড হচ্ছে…" : "Loading role contract…"}</div> : null}

    {contract ? <section className="admin-card admin-list-card">
      <div className="admin-table-wrap"><table className="admin-data-table admin-role-table">
        <thead><tr><th>{bn ? "Backend capability" : "Backend capability"}</th>{roles.map(role => <th key={role.role}>{role.role}<small>{role.users} users</small></th>)}</tr></thead>
        <tbody>{capabilities.map(capability => <tr key={capability}><td><strong>{labels[capability] || capability.replaceAll("_", " ")}</strong><small>{capability}</small></td>{roles.map(role => <td key={role.role}><Permission allowed={role.capabilities.includes(capability)} /></td>)}</tr>)}</tbody>
      </table></div>
    </section> : null}

    {roles.length ? <section className="admin-detail-grid">{roles.map(role => <article className="admin-card" key={role.role}><div className="admin-card__header"><div><h2>{role.role[0].toUpperCase() + role.role.slice(1)}</h2><p>{role.system_managed ? (bn ? "System-managed · deny by default" : "System-managed · deny by default") : (bn ? "Custom role" : "Custom role")}</p></div><span className="admin-status admin-status--active">{role.users} USERS</span></div><p className="admin-policy-copy">{role.role === "operator" ? (bn ? "Operator catalog ও supplier data দেখতে পারে, কিন্তু create/edit/archive শুধুই administrator করতে পারে।" : "Operators can read catalog and supplier data; create, edit and archive remain administrator-only.") : role.role === "customer" ? (bn ? "Customer শুধু নিজের account-owned data পায়।" : "Customers receive only account-owned data.") : (bn ? "Administrator operator capability-এর সঙ্গে policy, research ও management access পায়।" : "Administrators inherit operator capabilities and add policy, research and management access.")}</p></article>)}</section> : null}
  </div>;
}
