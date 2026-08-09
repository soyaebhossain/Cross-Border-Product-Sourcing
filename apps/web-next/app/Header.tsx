"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppIcon, type AppIconName } from "../components/app-icon";
import { getCurrentUser, logoutSession, type CurrentUser } from "../lib/api";
import { useLocale } from "../lib/locale-context";

export function Header() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const { locale, toggleLocale } = useLocale();
  const bn = locale === "bn";

  useEffect(() => { getCurrentUser().then(setCurrentUser).catch(() => setCurrentUser(null)); }, [pathname]);
  useEffect(() => setOpen(false), [pathname]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const target = `/products?q=${encodeURIComponent(search.trim())}`;
    window.location.assign(target);
  };
  const signOut = async () => {
    await logoutSession();
    setCurrentUser(null);
    router.push("/");
    router.refresh();
  };

  const isPrivileged = currentUser?.role === "admin" || currentUser?.role === "operator";
  const isAdmin = currentUser?.role === "admin";
  const nav: Array<[Route, string, AppIconName]> = isPrivileged
    ? [["/admin", bn ? "ড্যাশবোর্ড" : "Dashboard", "grid"], ["/admin/orders", bn ? "অর্ডার" : "Orders", "orders"], ["/admin/catalog", bn ? "ক্যাটালগ" : "Catalog", "package"], ...(isAdmin ? [["/research", bn ? "রিসার্চ" : "Research", "globe"] as [Route, string, AppIconName]] : [])]
    : [["/products", bn ? "পণ্য" : "Products", "package"], ["/categories", bn ? "ক্যাটাগরি" : "Categories", "grid"], ["/quote", bn ? "কোট নিন" : "Get a quote", "globe"], ["/account/orders", bn ? "আমার অর্ডার" : "My orders", "orders"]];
  const accountHref: Route = isPrivileged ? "/admin" : "/account";

  return <div className="header-stack"><header className={currentUser ? "site-header site-header--authenticated" : "site-header"}>
    <div className="site-header__brand"><Link href="/"><span className="brand-mark">S</span><span>Source<strong>AI</strong><small>{bn ? "সোর্সিং সিদ্ধান্তের মার্কেটপ্লেস" : "Decision-support marketplace"}</small></span></Link></div>
    <form className="global-search" onSubmit={submit} role="search"><span className="search-icon"><AppIcon name="search" size={18} /></span><input aria-label={bn ? "মার্কেটপ্লেসে খুঁজুন" : "Search marketplace"} value={search} onChange={event => setSearch(event.target.value)} placeholder={bn ? "পণ্য, মডেল বা ক্যাটাগরি খুঁজুন…" : "Search products, models, categories…"} /><button type="submit" aria-label={bn ? "পণ্য খুঁজুন" : "Search products"}><AppIcon name="search" size={17} /><span>{bn ? "খুঁজুন" : "Search"}</span></button></form>
    <button className="mobile-menu" type="button" aria-label={open ? (bn ? "নেভিগেশন বন্ধ করুন" : "Close navigation") : (bn ? "নেভিগেশন খুলুন" : "Open navigation")} aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen(value => !value)}><AppIcon name={open ? "close" : "menu"} size={22} /></button>
    <nav id="primary-navigation" aria-label="Primary navigation" className={open ? "site-header__nav site-header__nav--open" : "site-header__nav"}>
      {nav.map(([href, label, icon]) => <Link key={href} className={pathname === href || (href !== "/admin" && pathname.startsWith(href)) ? "nav-link nav-link--active" : "nav-link"} href={href}><AppIcon name={icon} size={16} />{label}</Link>)}
      {currentUser ? <Link className="nav-link mobile-account-link" href={accountHref}><AppIcon name="user" size={16} /><span>{bn ? "অ্যাকাউন্ট" : "Account"} · {currentUser.username || currentUser.email || `User ${currentUser.id}`}</span></Link> : null}
      {currentUser ? <button className="nav-link mobile-account-link mobile-signout" type="button" onClick={signOut}><AppIcon name="logout" size={16} />{bn ? "সাইন আউট" : "Sign out"}</button> : <Link className="nav-link mobile-account-link" href="/login"><AppIcon name="lock" size={16} />{bn ? "সাইন ইন" : "Sign in"}</Link>}
      <button className="locale-toggle locale-toggle--mobile" type="button" onClick={toggleLocale} aria-label={bn ? "ইংরেজি ভাষা বেছে নিন" : "Switch to Bangla"}><AppIcon name="language" size={16} />{bn ? "EN" : "বাংলা"}</button>
    </nav>
    <div className="site-header__action">
      <button className="locale-toggle" type="button" onClick={toggleLocale} aria-label={bn ? "ইংরেজি ভাষা বেছে নিন" : "Switch to Bangla"}><AppIcon name="language" size={16} /><span>{bn ? "EN" : "বাংলা"}</span></button>
      {currentUser ? <><Link className="account-chip" href={accountHref}><AppIcon name={isPrivileged ? "shield" : "user"} size={17} /><span><small>{isAdmin ? (bn ? "অ্যাডমিন" : "Admin") : currentUser.role === "operator" ? (bn ? "অপারেটর" : "Operator") : (bn ? "অ্যাকাউন্ট" : "Account")}</small><strong>{currentUser.username || currentUser.email || `User ${currentUser.id}`}</strong></span></Link><button className="button button--ghost header-logout" onClick={signOut} aria-label={bn ? "সাইন আউট" : "Sign out"}><AppIcon name="logout" size={17} /><span>{bn ? "সাইন আউট" : "Logout"}</span></button></> : <Link className="button button--primary header-signin" href="/login"><AppIcon name="lock" size={17} />{bn ? "সাইন ইন" : "Sign in"}</Link>}
    </div>
  </header><div className="trust-strip"><span><AppIcon name="check" size={14} />{bn ? "নিরাপদ সোর্সিং" : "Secure sourcing workflow"}</span><span><AppIcon name="check" size={14} />{bn ? "স্বচ্ছ ল্যান্ডেড কস্ট" : "Transparent landed cost"}</span><span><AppIcon name="check" size={14} />{bn ? "ব্যাখ্যাযোগ্য AI র‍্যাংকিং" : "Explainable AI ranking"}</span><span><AppIcon name="check" size={14} />{bn ? "সাপ্লায়ার ঝুঁকি সংকেত" : "Supplier risk signals"}</span></div></div>;
}
