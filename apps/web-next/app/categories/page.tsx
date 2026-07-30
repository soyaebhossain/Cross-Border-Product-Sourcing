"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppIcon } from "../../components/app-icon";
import { CategoryIcon } from "../../components/category-icon";
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
            <h1>Browse catalog segments</h1>
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
              <article className="category-chip category-directory-card" key={category.id}>
                <div className="category-directory-card__header">
                  <CategoryIcon name={category.name} />
                  <div className="category-directory-card__copy">
                    <h2>{category.name}</h2>
                    <p>Explore products, variants, and sourcing routes.</p>
                  </div>
                </div>
                <Link
                  className="category-directory-card__action"
                  href={`/products?category=${encodeURIComponent(category.slug)}`}
                >
                  Browse products <AppIcon name="arrow-right" size={16} />
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
