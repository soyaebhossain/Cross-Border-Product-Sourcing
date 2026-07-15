"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCategories, type Category } from "../../lib/api";

export default function CategoriesPage() {
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
            <p className="eyebrow">Categories</p>
            <h2>Browse catalog segments</h2>
          </div>
          <Link href="/quote" className="button button--primary">
            Request a quote
          </Link>
        </div>

        {loading ? (
          <div className="empty-state">Loading categories…</div>
        ) : error ? (
          <div className="empty-state">{error}</div>
        ) : categories.length === 0 ? (
          <div className="empty-state">
            <strong>No categories available yet.</strong>
            <p>The rebuild API may still be importing product metadata.</p>
          </div>
        ) : (
          <div className="category-grid">
            {categories.map((category) => (
              <div className="category-chip" key={category.id}>
                <strong>{category.name}</strong>
                <small>{category.slug}</small>
                <Link className="nav-link" href={`/quote?category=${encodeURIComponent(category.slug)}`}>
                  Request quote for this category
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
