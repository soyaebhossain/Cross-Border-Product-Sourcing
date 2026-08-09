"use client";

import Link from "next/link";
import type { Route } from "next";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Product, ProductVariant } from "./api";
import { getProductMedia } from "./api";
import { useLocale } from "./locale-context";
import { sourcingText } from "./sourcing-copy";

export type BasketItem = {
  key: string;
  productId: number;
  productName: string;
  productSlug: string;
  productModel: string | null;
  categoryName: string;
  imageSrc: string | null;
  imageAlt: string;
  imageKind: string;
  variantId: number;
  variantName: string;
  variants: ProductVariant[];
  quantity: number;
  moq: number;
  countryCode: string;
  availableCountries: string[];
  estimatedUnitPrice: number | null;
  currency: string;
  deliveryMinDays: number | null;
  riskLevel: string;
  supplierRating: number | null;
  supplierLabel: string;
  catalogPreview: boolean;
};

type AddProductOptions = {
  variantId?: number;
  quantity?: number;
  countryCode?: string;
};

type BasketContextValue = {
  items: BasketItem[];
  itemCount: number;
  estimatedProductTotal: number;
  addProduct: (product: Product, options?: AddProductOptions) => void;
  removeItem: (key: string) => void;
  updateItem: (key: string, patch: Partial<Pick<BasketItem, "variantId" | "variantName" | "quantity" | "countryCode">>) => void;
  clearBasket: () => void;
};

type LastMutation = {
  key: string;
  previous: BasketItem | null;
};

const STORAGE_KEY = "sourceai-sourcing-basket-v1";
const BasketContext = createContext<BasketContextValue | null>(null);

function itemKey(productId: number, variantId: number, countryCode: string) {
  return `${productId}:${variantId}:${countryCode}`;
}

function normalizeQuantity(value: number, moq = 1) {
  if (!Number.isFinite(value)) return moq;
  return Math.max(moq, Math.round(value));
}

function isStoredBasketItem(value: unknown): value is BasketItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<BasketItem>;
  return typeof item.key === "string"
    && typeof item.productId === "number"
    && typeof item.productName === "string"
    && typeof item.variantId === "number"
    && typeof item.quantity === "number";
}

export function SourcingBasketProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<BasketItem[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [toast, setToast] = useState<{ messageKey: "addedToBasket" | "alreadyInBasket"; productName: string } | null>(null);
  const [lastMutation, setLastMutation] = useState<LastMutation | null>(null);
  const { locale } = useLocale();

  useEffect(() => {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]") as unknown;
      if (Array.isArray(parsed)) setItems(parsed.filter(isStoredBasketItem));
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [hydrated, items]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const addProduct = (product: Product, options: AddProductOptions = {}) => {
    const variant = product.variants.find((row) => row.id === options.variantId)
      || product.variants.find((row) => row.id === product.default_variant_id)
      || product.variants[0];
    if (!variant) return;

    const availableCountries = product.market?.countries?.length ? product.market.countries : ["CN"];
    const countryCode = options.countryCode && availableCountries.includes(options.countryCode)
      ? options.countryCode
      : availableCountries[0];
    const key = itemKey(product.id, variant.id, countryCode);
    const existing = items.find((item) => item.key === key) || null;
    const media = getProductMedia(product)[0];
    const quantity = normalizeQuantity(options.quantity ?? 1);
    const nextItem: BasketItem = existing ? {
      ...existing,
      quantity: normalizeQuantity(existing.quantity + quantity, existing.moq),
    } : {
      key,
      productId: product.id,
      productName: product.name,
      productSlug: product.slug,
      productModel: product.model,
      categoryName: product.category.name,
      imageSrc: media?.src || null,
      imageAlt: media?.alt || product.name,
      imageKind: media?.kind || "illustrative",
      variantId: variant.id,
      variantName: variant.variant_name || variant.sku || `Variant ${variant.id}`,
      variants: product.variants,
      quantity,
      moq: 1,
      countryCode,
      availableCountries,
      estimatedUnitPrice: product.market?.min_price ?? null,
      currency: product.market?.currency || "USD",
      deliveryMinDays: product.market?.min_delivery_days ?? null,
      riskLevel: product.market?.risk_level || "Pending",
      supplierRating: product.market?.max_rating ?? null,
      supplierLabel: "Supplier selection pending",
      catalogPreview: product.catalog_source === "snapshot",
    };

    setItems((current) => existing
      ? current.map((item) => item.key === key ? nextItem : item)
      : [...current, nextItem]);
    setLastMutation({ key, previous: existing });
    setToast({ messageKey: existing ? "alreadyInBasket" : "addedToBasket", productName: product.name });
  };

  const removeItem = (key: string) => setItems((current) => current.filter((item) => item.key !== key));

  const updateItem = (key: string, patch: Partial<Pick<BasketItem, "variantId" | "variantName" | "quantity" | "countryCode">>) => {
    setItems((current) => current.map((item) => {
      if (item.key !== key) return item;
      const variantId = patch.variantId ?? item.variantId;
      const countryCode = patch.countryCode ?? item.countryCode;
      return {
        ...item,
        ...patch,
        key: itemKey(item.productId, variantId, countryCode),
        quantity: normalizeQuantity(patch.quantity ?? item.quantity, item.moq),
      };
    }));
  };

  const undoLastMutation = () => {
    if (!lastMutation) return;
    setItems((current) => {
      if (!lastMutation.previous) return current.filter((item) => item.key !== lastMutation.key);
      return current.map((item) => item.key === lastMutation.key ? lastMutation.previous! : item);
    });
    setToast(null);
    setLastMutation(null);
  };

  const itemCount = items.length;
  const estimatedProductTotal = items.reduce((total, item) => total + (item.estimatedUnitPrice || 0) * item.quantity, 0);
  const value = useMemo<BasketContextValue>(() => ({
    items,
    itemCount,
    estimatedProductTotal,
    addProduct,
    removeItem,
    updateItem,
    clearBasket: () => setItems([]),
  // addProduct intentionally follows the latest basket snapshot for duplicate handling.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [items, itemCount, estimatedProductTotal]);

  return <BasketContext.Provider value={value}>
    {children}
    {toast ? <div className="basket-toast" role="status" aria-live="polite">
      <div><strong>{sourcingText(locale, toast.messageKey)}</strong><span>{toast.productName}</span></div>
      <div className="basket-toast__actions">
        <Link href={"/sourcing-basket" as Route}>{sourcingText(locale, "viewBasket")}</Link>
        <button type="button" onClick={undoLastMutation}>{sourcingText(locale, "undo")}</button>
      </div>
    </div> : null}
    {itemCount ? <Link className="mobile-basket-bar" href={"/sourcing-basket" as Route} aria-label={`${sourcingText(locale, "basket")}: ${itemCount}`}>
      <span>{sourcingText(locale, "basket")}</span><strong>{itemCount}</strong>
    </Link> : null}
  </BasketContext.Provider>;
}

export function useSourcingBasket() {
  const context = useContext(BasketContext);
  if (!context) throw new Error("useSourcingBasket must be used within SourcingBasketProvider");
  return context;
}
