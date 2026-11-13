"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppIcon } from "../../components/app-icon";
import { CategoryIcon } from "../../components/category-icon";
import { getCategories, type Category } from "../../lib/api";
import { useLocale } from "../../lib/locale-context";

export default function CategoriesPage() {
  const { locale } = useLocale();
  const bn = locale === "bn";
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCategories()
      .then(setCategories)
      .catch(() => setError("Unable to load categories right now."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="shell shell--narrow">
      <div className="section">
        <div className="section__header">
          <div>
            <p className="eyebrow">{bn ? "ক্যাটাগরি" : "Categories"}</p>
            <h1>{bn ? "ক্যাটাগরি অনুযায়ী পণ্য দেখুন" : "Browse catalog segments"}</h1>
          </div>
          <Link href="/quote" className="button button--primary">
            {bn ? "কোট নিন" : "Request a quote"}
          </Link>
        </div>

        {loading ? (
          <div className="empty-state">{bn ? "ক্যাটাগরি লোড হচ্ছে…" : "Loading categories…"}</div>
        ) : error ? (
          <div className="empty-state">{bn ? "এই মুহূর্তে ক্যাটাগরি লোড করা যাচ্ছে না।" : error}</div>
        ) : categories.length === 0 ? (
          <div className="empty-state">
            <strong>{bn ? "এখনো কোনো ক্যাটাগরি নেই।" : "No categories available yet."}</strong>
            <p>{bn ? "ক্যাটালগের তথ্য এখনো তৈরি হচ্ছে। একটু পরে আবার দেখুন।" : "The rebuild API may still be importing product metadata."}</p>
          </div>
        ) : (
          <div className="category-grid">
            {categories.map((category) => (
              <article className="category-chip category-directory-card" key={category.id}>
                <div className="category-directory-card__header">
                  <CategoryIcon name={category.name} />
                  <div className="category-directory-card__copy">
                    <h2>{category.name}</h2>
                    <p>{bn ? "পণ্য, ভ্যারিয়েন্ট ও সোর্সিং রুট দেখুন।" : "Explore products, variants, and sourcing routes."}</p>
                  </div>
                </div>
                <Link
                  className="category-directory-card__action"
                  href={`/products?category=${encodeURIComponent(category.slug)}`}
                >
                  {bn ? "পণ্য দেখুন" : "Browse products"} <AppIcon name="arrow-right" size={16} />
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
