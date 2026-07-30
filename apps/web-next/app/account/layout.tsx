"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppIcon, type AppIconName } from "../../components/app-icon";
import { getCurrentUser, type CurrentUser } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { locale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => {
    let active = true;
    getCurrentUser().then(user => {
      if (!active) return;
      if (user.role === "admin" || user.role === "operator") {
        router.replace("/admin");
        return;
      }
      setUser(user);
      setReady(true);
    }).catch(() => router.replace("/login"));
    return () => { active = false; };
  }, [router]);

  if (!ready || !user) return <main className="shell shell--narrow"><div className="empty-state" aria-live="polite">{bn ? "অ্যাকাউন্ট যাচাই করা হচ্ছে…" : "Verifying account…"}</div></main>;

  const navigation: Array<{ href: Route; en: string; bn: string; icon: AppIconName; exact?: boolean }> = [
    { href: "/account", en: "Overview", bn: "ওভারভিউ", icon: "grid", exact: true },
    { href: "/account/orders", en: "My orders", bn: "আমার অর্ডার", icon: "orders" },
    { href: "/account/saved-quotes", en: "Saved quotes", bn: "সেভড কোট", icon: "globe" },
    { href: "/account/profile", en: "Profile & addresses", bn: "প্রোফাইল ও ঠিকানা", icon: "user" },
    { href: "/account/invoices", en: "Invoices", bn: "ইনভয়েস", icon: "package" },
    { href: "/account/notifications", en: "Notifications", bn: "নোটিফিকেশন", icon: "alert" },
    { href: "/account/support", en: "Support & disputes", bn: "সাপোর্ট ও dispute", icon: "shield" },
  ];

  return (
    <main className="shell account-shell">
      <div className="account-layout">
        <aside className="account-sidebar">
          <div className="account-sidebar__identity">
            <span aria-hidden>{(user.username || user.email || "U").slice(0, 1).toUpperCase()}</span>
            <div><strong>{user.username || user.email || `User #${user.id}`}</strong><small>{bn ? "কাস্টমার অ্যাকাউন্ট" : "Customer account"}</small></div>
          </div>
          <nav aria-label={bn ? "অ্যাকাউন্ট নেভিগেশন" : "Account navigation"}>
            {navigation.map(item => {
              const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
              return <Link key={item.href} className={active ? "account-sidebar__link account-sidebar__link--active" : "account-sidebar__link"} href={item.href} aria-current={active ? "page" : undefined}><AppIcon name={item.icon} size={16} />{bn ? item.bn : item.en}</Link>;
            })}
          </nav>
          <p>{bn ? "আপনি শুধু নিজের অর্ডার ও কোট দেখতে পারবেন।" : "You can only access your own orders and quotes."}</p>
        </aside>
        <div className="account-content">
          <div className="account-mobile-nav">
            <label><span className="sr-only">{bn ? "অ্যাকাউন্ট পৃষ্ঠা" : "Account page"}</span>
              <select value={navigation.find(item => item.exact ? pathname === item.href : pathname.startsWith(item.href))?.href || "/account"} onChange={event => router.push(event.target.value as Route)}>
                {navigation.map(item => <option key={item.href} value={item.href}>{bn ? item.bn : item.en}</option>)}
              </select>
            </label>
          </div>
          {children}
        </div>
      </div>
    </main>
  );
}
