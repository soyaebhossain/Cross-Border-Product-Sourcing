"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser, logoutSession, type CurrentUser } from "../lib/api";
import { useLocale } from "../lib/locale-context";

function SearchIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="m16 16 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

function MenuIcon({ open }: { open: boolean }) {
  return <svg viewBox="0 0 24 24" aria-hidden>{open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg>;
}

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
  const nav: Array<[Route, string]> = isPrivileged
    ? [["/admin", bn ? "ড্যাশবোর্ড" : "Dashboard"], ["/admin/orders", bn ? "অর্ডার" : "Orders"], ["/admin/catalog", bn ? "ক্যাটালগ" : "Catalog"], ...(isAdmin ? [["/research", bn ? "রিসার্চ" : "Research"] as [Route, string]] : [])]
    : [["/products", bn ? "পণ্য" : "Products"], ["/categories", bn ? "ক্যাটাগরি" : "Categories"], ["/quote", bn ? "কোট নিন" : "Get a quote"], ["/account/orders", bn ? "আমার অর্ডার" : "My orders"]];
  const accountHref: Route = isPrivileged ? "/admin" : "/account";

  return <div className="header-stack"><header className="site-header">
    <div className="site-header__brand"><Link href="/"><span className="brand-mark">S</span><span>Source<strong>AI</strong><small>{bn ? "সোর্সিং সিদ্ধান্তের মার্কেটপ্লেস" : "Decision-support marketplace"}</small></span></Link></div>
    <form className="global-search" onSubmit={submit} role="search"><span className="search-icon"><SearchIcon /></span><input aria-label={bn ? "মার্কেটপ্লেসে খুঁজুন" : "Search marketplace"} value={search} onChange={event => setSearch(event.target.value)} placeholder={bn ? "পণ্য, মডেল বা ক্যাটাগরি খুঁজুন…" : "Search products, models, categories…"} /><button type="submit">{bn ? "খুঁজুন" : "Search"}</button></form>
    <button className="mobile-menu" type="button" aria-label={bn ? "নেভিগেশন খুলুন" : "Toggle navigation"} aria-expanded={open} aria-controls="primary-navigation" onClick={() => setOpen(value => !value)}><MenuIcon open={open} /></button>
    <nav id="primary-navigation" aria-label="Primary navigation" className={open ? "site-header__nav site-header__nav--open" : "site-header__nav"}>
      {nav.map(([href, label]) => <Link key={href} className={pathname === href || (href !== "/admin" && pathname.startsWith(href)) ? "nav-link nav-link--active" : "nav-link"} href={href}>{label}</Link>)}
      {currentUser ? <Link className="nav-link mobile-account-link" href={accountHref}>{bn ? "অ্যাকাউন্ট" : "Account"} · {currentUser.username || currentUser.email || `User ${currentUser.id}`}</Link> : null}
      {currentUser ? <button className="nav-link mobile-account-link mobile-signout" type="button" onClick={signOut}>{bn ? "সাইন আউট" : "Sign out"}</button> : <Link className="nav-link mobile-account-link" href="/login">{bn ? "সাইন ইন" : "Sign in"}</Link>}
      <button className="locale-toggle locale-toggle--mobile" type="button" onClick={toggleLocale} aria-label={bn ? "ইংরেজি ভাষা বেছে নিন" : "Switch to Bangla"}>{bn ? "EN" : "বাংলা"}</button>
    </nav>
    <div className="site-header__action">
      <button className="locale-toggle" type="button" onClick={toggleLocale} aria-label={bn ? "ইংরেজি ভাষা বেছে নিন" : "Switch to Bangla"}>{bn ? "EN" : "বাংলা"}</button>
      {currentUser ? <><Link className="account-chip" href={accountHref}><span>{isAdmin ? (bn ? "অ্যাডমিন" : "Admin") : currentUser.role === "operator" ? (bn ? "অপারেটর" : "Operator") : (bn ? "অ্যাকাউন্ট" : "Account")}</span><strong>{currentUser.username || currentUser.email || `User ${currentUser.id}`}</strong></Link><button className="button button--ghost" onClick={signOut}>{bn ? "সাইন আউট" : "Logout"}</button></> : <Link className="button button--primary" href="/login">{bn ? "সাইন ইন" : "Sign in"}</Link>}
    </div>
  </header><div className="trust-strip"><span>{bn ? "নিরাপদ সোর্সিং" : "Secure sourcing workflow"}</span><span>{bn ? "স্বচ্ছ ল্যান্ডেড কস্ট" : "Transparent landed cost"}</span><span>{bn ? "ব্যাখ্যাযোগ্য AI র‍্যাংকিং" : "Explainable AI ranking"}</span><span>{bn ? "সাপ্লায়ার ঝুঁকি সংকেত" : "Supplier risk signals"}</span></div></div>;
}
