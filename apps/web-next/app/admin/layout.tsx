"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AppIcon } from "../../components/app-icon";
import { getCurrentUser, type CurrentUser } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

type IconName = "overview" | "orders" | "payments" | "quotes" | "support" | "disputes" | "notifications" | "catalog" | "suppliers" | "users" | "rules" | "roles" | "audit" | "settings";

function AdminIcon({ name }: { name: IconName }) {
  const paths: Record<IconName, React.ReactNode> = {
    overview: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    orders: <><path d="M6 3h12l2 4v14H4V7l2-4Z" /><path d="M4 8h16M9 12h6" /></>,
    payments: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18M7 15h3" /></>,
    quotes: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" /><path d="M9 8h6M9 12h6" /></>,
    support: <><path d="M4 5h16v12H8l-4 4V5Z" /><path d="M8 9h8M8 13h5" /></>,
    disputes: <><path d="M12 3 4 6v5c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6l-8-3Z" /><path d="M12 8v5M12 16h.01" /></>,
    notifications: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z" /><path d="M10 21h4" /></>,
    catalog: <><path d="m4 7 8-4 8 4-8 4-8-4Z" /><path d="m4 12 8 4 8-4M4 17l8 4 8-4" /></>,
    suppliers: <><path d="M3 21V8l6-4v17M9 11l6-4v14M15 13l6-3v11" /><path d="M6 10v2M12 12v2M18 14v2" /></>,
    users: <><circle cx="9" cy="8" r="4" /><path d="M2 21c0-4 3-7 7-7s7 3 7 7M16 5c3 0 5 2 5 5M17 15c3 1 5 3 5 6" /></>,
    rules: <><path d="M4 4h16v16H4zM8 8h8M8 12h8M8 16h5" /><circle cx="18" cy="16" r="2" /></>,
    roles: <><path d="M12 3 4 6v5c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6l-8-3Z" /><path d="m9 12 2 2 4-5" /></>,
    audit: <><path d="M5 3h14v18H5z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
  };
  return <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuToggleRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const menuWasOpenRef = useRef(false);
  const pathname = usePathname();
  const router = useRouter();
  const { locale } = useLocale();
  const bn = locale === "bn";

  const trapNavigationFocus = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Tab" || !menuOpen || window.innerWidth > 820) return;
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>("a[href], button:not([disabled])"),
    ).filter(element => element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((current) => {
        if (!active) return;
        if (current.role !== "admin" && current.role !== "operator") {
          router.replace("/account/orders");
          return;
        }
        setUser(current);
      })
      .catch(() => router.replace("/login?portal=admin"))
      .finally(() => active && setChecking(false));
    return () => { active = false; };
  }, [router]);
  useEffect(() => setMenuOpen(false), [pathname]);
  useEffect(() => {
    if (!menuOpen) {
      if (menuWasOpenRef.current) {
        menuWasOpenRef.current = false;
        const toggle = menuToggleRef.current;
        if (toggle && toggle.offsetParent !== null) {
          toggle.focus();
        } else {
          document.querySelector<HTMLElement>("#admin-navigation [aria-current='page']")?.focus();
        }
      }
      return;
    }
    menuWasOpenRef.current = true;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    const closeAtDesktopLayout = () => {
      if (window.innerWidth > 820) setMenuOpen(false);
    };
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("resize", closeAtDesktopLayout);
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", closeAtDesktopLayout);
    };
  }, [menuOpen]);
  useEffect(() => {
    if (user?.role === "operator" && ["/admin/users", "/admin/roles", "/admin/rules", "/admin/audit"].some(path => pathname.startsWith(path))) {
      router.replace("/admin");
    }
  }, [pathname, router, user]);

  const navigation: Array<{ href: Route; icon: IconName; en: string; bn: string; adminOnly?: boolean }> = [
    { href: "/admin", icon: "overview", en: "Overview", bn: "ওভারভিউ" },
    { href: "/admin/analytics", icon: "overview", en: "Analytics", bn: "অ্যানালিটিক্স" },
    { href: "/admin/orders", icon: "orders", en: "Orders", bn: "অর্ডার" },
    { href: "/admin/payments", icon: "payments", en: "Payments", bn: "পেমেন্ট" },
    { href: "/admin/quotes", icon: "quotes", en: "Saved quotes", bn: "সেভড কোট" },
    { href: "/admin/ai-reviews", icon: "quotes", en: "AI review queue", bn: "AI রিভিউ কিউ" },
    { href: "/admin/catalog", icon: "catalog", en: "Products & categories", bn: "পণ্য ও ক্যাটাগরি" },
    { href: "/admin/suppliers", icon: "suppliers", en: "Suppliers & offers", bn: "সাপ্লায়ার ও অফার" },
    { href: "/admin/users", icon: "users", en: "Customers & users", bn: "কাস্টমার ও ইউজার", adminOnly: true },
    { href: "/admin/rules", icon: "rules", en: "Shipping, currency & duty", bn: "শিপিং, মুদ্রা ও শুল্ক", adminOnly: true },
    { href: "/admin/roles", icon: "roles", en: "Roles & permissions", bn: "রোল ও অনুমতি", adminOnly: true },
    { href: "/admin/audit", icon: "audit", en: "Audit log", bn: "অডিট লগ", adminOnly: true },
    { href: "/admin/settings", icon: "settings", en: "Settings", bn: "সেটিংস" },
  ];
  navigation.splice(
    5,
    0,
    { href: "/admin/support", icon: "support", en: "Support tickets", bn: "সাপোর্ট টিকিট" },
    { href: "/admin/disputes", icon: "disputes", en: "Disputes", bn: "কাস্টমার বিরোধ" },
    { href: "/admin/notifications", icon: "notifications", en: "Notification outbox", bn: "নোটিফিকেশন আউটবক্স" },
  );

  if (checking || !user || (user.role === "operator" && ["/admin/users", "/admin/roles", "/admin/rules", "/admin/audit"].some(path => pathname.startsWith(path)))) {
    return <main className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "অ্যাক্সেস যাচাই করা হচ্ছে…" : "Verifying admin access…"}</main>;
  }

  return (
    <main className="admin-app">
      <button ref={menuToggleRef} className="admin-sidebar-toggle" type="button" aria-expanded={menuOpen} aria-controls="admin-navigation" onClick={() => setMenuOpen(value => !value)}>
        <AdminIcon name="overview" /><span>{bn ? "অ্যাডমিন মেনু" : "Admin menu"}</span><AppIcon name="chevron-down" size={17} />
      </button>
      {menuOpen ? <button className="admin-sidebar-backdrop" type="button" aria-label={bn ? "অ্যাডমিন মেনু বন্ধ করুন" : "Close admin menu"} onClick={() => setMenuOpen(false)} /> : null}
      <aside
        id="admin-navigation"
        aria-label={bn ? "অ্যাডমিন নেভিগেশন" : "Admin navigation"}
        aria-modal={menuOpen ? true : undefined}
        className={menuOpen ? "admin-sidebar admin-sidebar--open" : "admin-sidebar"}
        onKeyDown={trapNavigationFocus}
        role={menuOpen ? "dialog" : undefined}
      >
        <div className="admin-sidebar__identity">
          <span className="admin-sidebar__avatar" aria-hidden>{(user.username || user.email || "A").slice(0, 1).toUpperCase()}</span>
          <div><strong>{user.username || user.email || `User ${user.id}`}</strong><span>{user.role === "operator" ? (bn ? "অপারেটর" : "Operator") : (bn ? "অ্যাডমিনিস্ট্রেটর" : "Administrator")}</span></div>
          <button ref={closeButtonRef} className="admin-sidebar__close" type="button" aria-label={bn ? "অ্যাডমিন মেনু বন্ধ করুন" : "Close admin menu"} onClick={() => setMenuOpen(false)}><AppIcon name="close" size={20} /></button>
        </div>
        <nav aria-label={bn ? "অ্যাডমিন নেভিগেশন" : "Admin navigation"}>
          {navigation.filter(item => !item.adminOnly || user.role === "admin").map(item => {
            const active = item.href === "/admin" ? pathname === item.href : pathname.startsWith(item.href);
            return <Link key={item.href} href={item.href} className={active ? "admin-sidebar__link admin-sidebar__link--active" : "admin-sidebar__link"} aria-current={active ? "page" : undefined}><AdminIcon name={item.icon} /><span>{bn ? item.bn : item.en}</span></Link>;
          })}
        </nav>
        <div className="admin-sidebar__footer">
          <span>{bn ? "প্রোডাকশন অপারেশন" : "Production operations"}</span>
          <small>{bn ? "Asia/Dhaka সময়" : "Asia/Dhaka timezone"}</small>
        </div>
      </aside>
      <div className="admin-main">{children}</div>
    </main>
  );
}
