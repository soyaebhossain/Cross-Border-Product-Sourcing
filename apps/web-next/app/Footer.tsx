"use client";

import Link from "next/link";
import { useLocale } from "../lib/locale-context";

export function Footer() {
  const { locale } = useLocale();
  const bn = locale === "bn";
  return (
    <footer className="market-footer">
      <div className="footer-grid">
        <div>
          <div className="footer-brand">
            <span className="brand-mark">S</span>Source<strong>AI</strong>
          </div>
          <p>
            {bn
              ? "দক্ষ cross-border product sourcing-এর জন্য AI-সহায়িত decision-support marketplace।"
              : "A Decision-Support Marketplace Using Artificial Intelligence for Efficient Cross-Border Product Sourcing."}
          </p>
        </div>
        <div>
          <strong>{bn ? "মার্কেটপ্লেস" : "Marketplace"}</strong>
          <Link href="/products">{bn ? "পণ্য দেখুন" : "Browse products"}</Link>
          <Link href="/categories">{bn ? "ক্যাটাগরি" : "Categories"}</Link>
          <Link href="/quote">{bn ? "কোট নিন" : "Request quotation"}</Link>
        </div>
        <div>
          <strong>{bn ? "সিদ্ধান্তের টুল" : "Decision tools"}</strong>
          <Link href="/quote">{bn ? "সোর্সিং রুট তুলনা" : "Compare sourcing routes"}</Link>
          <Link href="/account/saved-quotes">{bn ? "সেভড কোট" : "Saved quotes"}</Link>
          <Link href="/account/orders">{bn ? "অর্ডার ট্র্যাক" : "Track orders"}</Link>
        </div>
        <div>
          <strong>{bn ? "বিশ্বাসের ভিত্তি" : "Built for trust"}</strong>
          <span>{bn ? "স্বচ্ছ খরচ" : "Cost transparency"}</span>
          <span>{bn ? "সাপ্লায়ার নির্ভরযোগ্যতা" : "Supplier reliability"}</span>
          <span>{bn ? "ঝুঁকি-সচেতন পরামর্শ" : "Risk-aware recommendations"}</span>
        </div>
      </div>
      <div className="footer-bottom">
        <span>
          © {new Date().getFullYear()} SourceAI. {bn ? "সর্বস্বত্ব সংরক্ষিত।" : "All rights reserved."}
        </span>
        <span>{bn ? "SourceAI-এর নিজস্ব প্ল্যাটফর্ম" : "A SourceAI-owned platform"}</span>
      </div>
    </footer>
  );
}
