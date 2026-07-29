"use client";

import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import type { AdminUserRow } from "../../../lib/api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

export default function AdminUsersPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const columns: AdminColumn<AdminUserRow>[] = [
    { key: "user", label: bn ? "ইউজার" : "User", cell: row => <div className="admin-primary-cell"><strong>{row.username || `User #${row.id}`}</strong><small>{row.email || row.phone || `ID ${row.id}`}</small></div>, exportValue: row => `${row.username || ""} ${row.email || ""} ${row.phone || ""}`, sortValue: row => row.username || row.email },
    { key: "role", label: bn ? "রোল" : "Role", cell: row => <span className={`admin-status admin-status--${row.role.toLowerCase()}`}>{row.role}</span>, exportValue: row => row.role, sortValue: row => row.role },
    { key: "status", label: bn ? "অ্যাকাউন্ট" : "Account", cell: row => <span className={`admin-status admin-status--${row.is_active === false ? "inactive" : "active"}`}>{row.is_active === false ? (bn ? "নিষ্ক্রিয়" : "Inactive") : (bn ? "সক্রিয়" : "Active")}</span>, exportValue: row => row.is_active === false ? "Inactive" : "Active", sortValue: row => row.is_active === false ? 0 : 1 },
    { key: "joined", label: bn ? "যোগ দিয়েছেন" : "Joined", cell: row => formatDateTime(row.created_at, intlLocale), exportValue: row => row.created_at, sortValue: row => row.created_at },
  ];
  return <AdminDataPage<AdminUserRow>
    resource="users"
    eyebrow={bn ? "অ্যাক্সেস কন্ট্রোল" : "Access control"}
    title={bn ? "ইউজার ও রোল" : "Users and roles"}
    description={bn ? "Customer, operator ও administrator account আলাদাভাবে পর্যবেক্ষণ করুন।" : "Review customer, operator and administrator accounts separately."}
    searchPlaceholder={bn ? "নাম, email বা phone খুঁজুন" : "Search name, email or phone"}
    columns={columns}
    filters={[{ key: "role", label: bn ? "রোল" : "Role", options: ["customer", "operator", "admin"].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) })) }]}
    detailHref={row => `/admin/users/${row.id}`}
  />;
}
