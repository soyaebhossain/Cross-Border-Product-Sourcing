"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import { ProductImage } from "../../../../components/product-image";
import { updateAdminProduct } from "../../../../lib/admin-api";
import { getAdminList, type AdminProductRow } from "../../../../lib/api";
import { useAdminAccess } from "../../../../lib/use-admin-access";
import { useLocale } from "../../../../lib/locale-context";
import { hasAssignedProductImage, validateProductImageLocation } from "./media-utils";
import styles from "./media.module.css";

type MediaFilter = "all" | "ready" | "missing";

const pageSize = 24;

function productCategory(product: AdminProductRow) {
  return typeof product.category === "string"
    ? product.category
    : product.category?.name || "Uncategorised";
}

export default function AdminCatalogMediaPage() {
  const [products, setProducts] = useState<AdminProductRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>("missing");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminProductRow | null>(null);
  const [imageLocation, setImageLocation] = useState("");
  const [auditNote, setAuditNote] = useState("");
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";

  const loadProducts = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const first = await getAdminList<AdminProductRow>("products", { page: 1, page_size: 100 });
      const remainingPages = await Promise.all(
        Array.from({ length: Math.max(first.pages - 1, 0) }, (_, index) => (
          getAdminList<AdminProductRow>("products", { page: index + 2, page_size: 100 })
        )),
      );
      const items = [first, ...remainingPages].flatMap(result => result.items);
      setProducts(items);
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "Product media inventory could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadProducts(); }, [loadProducts]);
  useEffect(() => { setPage(1); }, [query, category, mediaFilter]);

  const readyCount = useMemo(
    () => products.filter(product => hasAssignedProductImage(product.image)).length,
    [products],
  );
  const missingCount = products.length - readyCount;
  const coverage = products.length ? Math.round((readyCount / products.length) * 100) : 0;
  const categories = useMemo(
    () => [...new Set(products.map(productCategory))].sort((left, right) => left.localeCompare(right, intlLocale)),
    [products, intlLocale],
  );
  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase(intlLocale);
    return products.filter(product => {
      const ready = hasAssignedProductImage(product.image);
      if (mediaFilter === "ready" && !ready) return false;
      if (mediaFilter === "missing" && ready) return false;
      if (category && productCategory(product) !== category) return false;
      if (!normalizedQuery) return true;
      return `${product.name} ${product.model || ""} ${product.slug || ""} ${productCategory(product)}`
        .toLocaleLowerCase(intlLocale)
        .includes(normalizedQuery);
    });
  }, [products, query, category, mediaFilter, intlLocale]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visibleProducts = filtered.slice((page - 1) * pageSize, page * pageSize);

  const openEditor = (product: AdminProductRow) => {
    setEditing(product);
    setImageLocation(product.image || "");
    setAuditNote("");
    setFormError("");
  };

  const validationError = imageLocation ? validateProductImageLocation(imageLocation) : "";
  const previewLocation = imageLocation && !validationError ? imageLocation.trim() : editing?.image || null;

  const saveImage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editing || !isAdmin) return;
    const validation = validateProductImageLocation(imageLocation);
    if (validation) {
      setFormError(validation);
      return;
    }
    if (auditNote.trim().length < 3) {
      setFormError("Add a short audit note explaining the image source.");
      return;
    }

    setSaving(true);
    setFormError("");
    try {
      const updated = await updateAdminProduct(editing.id, {
        image: imageLocation.trim(),
        note: auditNote.trim(),
      });
      setProducts(current => current.map(product => (
        product.id === updated.id ? { ...product, image: updated.image } : product
      )));
      setEditing(null);
      setToast(bn ? "পণ্যের ছবি audit log-সহ সংরক্ষণ হয়েছে।" : "Product image saved with an audit record.");
      window.setTimeout(() => setToast(""), 3600);
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "Product image could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  return <>
    <nav className="admin-subnav" aria-label={bn ? "Catalog section" : "Catalog sections"}>
      <Link href="/admin/catalog">{bn ? "পণ্য" : "Products"}</Link>
      <Link href="/admin/catalog/categories">{bn ? "ক্যাটাগরি" : "Categories"}</Link>
      <Link href="/admin/catalog/variants">{bn ? "ভ্যারিয়েন্ট" : "Variants"}</Link>
      <Link className="admin-subnav--active" href="/admin/catalog/media">{bn ? "ছবি" : "Product media"}</Link>
    </nav>

    <div className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="admin-eyebrow">{bn ? "Catalog quality" : "Catalog quality"}</p>
          <h1>{bn ? "পণ্যের ছবি" : "Product media"}</h1>
          <p>{bn ? "বাস্তব supplier-approved ছবি যোগ করুন এবং fallback illustration কমান।" : "Assign real, supplier-approved product images and reduce reliance on fallback illustrations."}</p>
        </div>
        <div className="admin-toolbar">
          {!isAdmin ? <span className="admin-read-only">{bn ? "Operator · শুধু দেখুন" : "Operator · read only"}</span> : null}
          <button className="admin-button admin-button--secondary" type="button" onClick={() => void loadProducts()} disabled={loading}>
            {loading ? (bn ? "লোড হচ্ছে…" : "Loading…") : (bn ? "রিফ্রেশ" : "Refresh")}
          </button>
        </div>
      </header>

      <div className={styles.summaryGrid} aria-label={bn ? "ছবির কভারেজ" : "Image coverage"}>
        <article className={styles.summaryCard}><span>{bn ? "মোট পণ্য" : "Total products"}</span><strong>{new Intl.NumberFormat(intlLocale).format(products.length)}</strong><small>{bn ? "সম্পূর্ণ catalog inventory" : "Complete catalog inventory"}</small></article>
        <article className={styles.summaryCard}><span>{bn ? "ছবি দেওয়া" : "Image assigned"}</span><strong>{new Intl.NumberFormat(intlLocale).format(readyCount)}</strong><small>{bn ? "নিজস্ব বা অনুমোদিত image path" : "Owned or approved image path"}</small></article>
        <article className={styles.summaryCard}><span>{bn ? "ছবি প্রয়োজন" : "Needs image"}</span><strong>{new Intl.NumberFormat(intlLocale).format(missingCount)}</strong><small>{bn ? "বর্তমানে professional fallback ব্যবহার করছে" : "Currently using the professional fallback"}</small></article>
        <article className={styles.summaryCard}><span>{bn ? "কভারেজ" : "Coverage"}</span><strong>{coverage}%</strong><small>{bn ? "Image assignment completeness" : "Image assignment completeness"}</small><div className={styles.coverageTrack} aria-hidden><span style={{ width: `${coverage}%` }} /></div></article>
      </div>

      <div className={styles.guidance}>
        <strong>{bn ? "Professional media policy" : "Professional media policy"}</strong>
        <span>{bn ? "HTTPS CDN/supplier-approved URL অথবা /media/products/ path ব্যবহার করুন। Random placeholder hotlink গ্রহণ করা হবে না। Binary upload-এর জন্য object storage backend প্রয়োজন।" : "Use an HTTPS CDN/supplier-approved URL or a /media/products/ path. Random placeholder hotlinks are rejected. Binary upload requires an object-storage backend."}</span>
      </div>

      <section className="admin-card admin-list-card">
        <div className={styles.toolbar}>
          <label className={styles.field}><span>{bn ? "পণ্য খুঁজুন" : "Search products"}</span><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={bn ? "নাম, model বা slug" : "Name, model or slug"} /></label>
          <label className={styles.field}><span>{bn ? "ছবির অবস্থা" : "Media status"}</span><select value={mediaFilter} onChange={event => setMediaFilter(event.target.value as MediaFilter)}><option value="missing">{bn ? "ছবি প্রয়োজন" : "Needs image"}</option><option value="ready">{bn ? "ছবি দেওয়া" : "Image assigned"}</option><option value="all">{bn ? "সব পণ্য" : "All products"}</option></select></label>
          <label className={styles.field}><span>{bn ? "ক্যাটাগরি" : "Category"}</span><select value={category} onChange={event => setCategory(event.target.value)}><option value="">{bn ? "সব ক্যাটাগরি" : "All categories"}</option>{categories.map(item => <option value={item} key={item}>{item}</option>)}</select></label>
        </div>

        {loadError ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Unable to load"}</strong><span>{loadError}</span><button type="button" onClick={() => void loadProducts()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div> : null}
        {loading && !products.length ? <div className={styles.loading}>{bn ? "Product media inventory লোড হচ্ছে…" : "Loading the product media inventory…"}</div> : null}
        {!loading && !loadError && !visibleProducts.length ? <div className={styles.empty}><div><strong>{bn ? "কোনো matching product নেই" : "No matching products"}</strong><p>{bn ? "Search বা filter পরিবর্তন করে দেখুন।" : "Try changing the search or filters."}</p></div></div> : null}

        {visibleProducts.length ? <div className={styles.grid}>{visibleProducts.map(product => {
          const ready = hasAssignedProductImage(product.image);
          const categoryName = productCategory(product);
          return <article className={styles.productCard} key={product.id}>
            <div className={styles.productVisual}>
              <ProductImage
                src={product.image}
                name={product.name}
                category={categoryName}
                sourceKind={product.image?.includes("/illustrative/") ? "illustrative" : undefined}
              />
              <span className={`${styles.status} ${ready ? styles.statusReady : ""}`}>{ready ? (bn ? "ছবি দেওয়া" : "Assigned") : (bn ? "ছবি প্রয়োজন" : "Needs image")}</span>
            </div>
            <div className={styles.productBody}>
              <p>{categoryName}</p>
              <h2>{product.name}</h2>
              <code title={product.image || undefined}>{product.image || (bn ? "Professional fallback illustration" : "Professional fallback illustration")}</code>
              <div className={styles.cardActions}>
                <Link href={`/admin/catalog/${product.id}`}>{bn ? "বিস্তারিত" : "Details"}</Link>
                <button type="button" onClick={() => openEditor(product)} disabled={!isAdmin}>{ready ? (bn ? "ছবি বদলান" : "Replace image") : (bn ? "ছবি যোগ করুন" : "Add image")}</button>
              </div>
            </div>
          </article>;
        })}</div> : null}

        <footer className={styles.pagination}>
          <span>{new Intl.NumberFormat(intlLocale).format(filtered.length)} {bn ? "টি matching product" : "matching products"} · {bn ? "পৃষ্ঠা" : "Page"} {page}/{pages}</span>
          <div><button type="button" disabled={page <= 1} onClick={() => setPage(current => Math.max(1, current - 1))}>{bn ? "আগের" : "Previous"}</button><button type="button" disabled={page >= pages} onClick={() => setPage(current => Math.min(pages, current + 1))}>{bn ? "পরের" : "Next"}</button></div>
        </footer>
      </section>
    </div>

    <AdminModal
      open={editing !== null}
      onClose={() => !saving && setEditing(null)}
      title={editing && hasAssignedProductImage(editing.image) ? (bn ? "পণ্যের ছবি বদলান" : "Replace product image") : (bn ? "পণ্যের ছবি যোগ করুন" : "Add product image")}
      description={editing ? `${editing.name} · ${productCategory(editing)}` : ""}
    >
      <form className="admin-modal__form" onSubmit={saveImage}>
        {editing ? <div className={styles.modalPreview}>
          <ProductImage
            src={previewLocation}
            name={editing.name}
            category={productCategory(editing)}
            sourceKind={previewLocation?.includes("/illustrative/") ? "illustrative" : undefined}
          />
          <div><strong>{bn ? "Preview" : "Preview"}</strong><p>{bn ? "Image load না হলে public catalog নিরাপদ fallback দেখাবে।" : "If the image cannot load, the public catalog keeps a safe fallback."}</p></div>
        </div> : null}
        <label><span>{bn ? "HTTPS image URL অথবা public path" : "HTTPS image URL or public path"}</span><input type="text" maxLength={500} required placeholder="https://cdn.example.com/product.webp or /media/products/product.webp" value={imageLocation} onChange={event => { setImageLocation(event.target.value); setFormError(""); }} />{validationError ? <small className={styles.formError}>{validationError}</small> : null}</label>
        <label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} rows={3} required placeholder={bn ? "ছবির উৎস ও ব্যবহারের অনুমতি লিখুন" : "Document the source and permission to use this image"} value={auditNote} onChange={event => { setAuditNote(event.target.value); setFormError(""); }} /></label>
        {formError ? <div className="admin-alert admin-alert--error" role="alert">{formError}</div> : null}
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setEditing(null)} disabled={saving}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || Boolean(validationError) || auditNote.trim().length < 3}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "ছবি সংরক্ষণ" : "Save image")}</button></div>
      </form>
    </AdminModal>
    {toast ? <div className={styles.toast} role="status">{toast}</div> : null}
  </>;
}
