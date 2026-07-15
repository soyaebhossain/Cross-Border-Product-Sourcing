"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser, logoutSession } from "../lib/api";

function SearchIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="m16 16 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

function MenuIcon({ open }: { open: boolean }) {
  return <svg viewBox="0 0 24 24" aria-hidden>{open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg>;
}

export function Header() {
  const [authenticated, setAuthenticated] = useState(false);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => { getCurrentUser().then(() => setAuthenticated(true)).catch(() => setAuthenticated(false)); }, [pathname]);
  useEffect(() => setOpen(false), [pathname]);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const target = `/products?q=${encodeURIComponent(search.trim())}`;
    window.location.assign(target);
  };
  const nav = [["/products", "Products"], ["/categories", "Categories"], ["/quote", "Get a quote"], ["/account/orders", "Orders"], ["/research", "Research"]] as const;

  return <div className="header-stack"><header className="site-header">
    <div className="site-header__brand"><Link href="/"><span className="brand-mark">S</span><span>Source<strong>AI</strong><small>Decision-support marketplace</small></span></Link></div>
    <form className="global-search" onSubmit={submit} role="search"><span className="search-icon"><SearchIcon /></span><input aria-label="Search marketplace" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search products, models, categories…" /><button type="submit">Search</button></form>
    <button className="mobile-menu" type="button" aria-label="Toggle navigation" aria-expanded={open} onClick={() => setOpen(value => !value)}><MenuIcon open={open} /></button>
    <nav className={open ? "site-header__nav site-header__nav--open" : "site-header__nav"}>{nav.map(([href, label]) => <Link key={href} className={pathname.startsWith(href) ? "nav-link nav-link--active" : "nav-link"} href={href}>{label}</Link>)}</nav>
    <div className="site-header__action">{authenticated ? <button className="button button--ghost" onClick={async () => { await logoutSession(); setAuthenticated(false); router.push("/"); router.refresh(); }}>Logout</button> : <Link className="button button--primary" href="/login">Sign in</Link>}</div>
  </header><div className="trust-strip"><span>Secure sourcing workflow</span><span>Transparent landed cost</span><span>Explainable AI ranking</span><span>Supplier risk signals</span></div></div>;
}
