"use client";

import { createContext, useContext, useMemo, useState } from "react";

type ProductQuantity = { quantity: number; setQuantity: (value: number) => void };

const ProductQuantityContext = createContext<ProductQuantity | null>(null);

/**
 * One quantity for the whole product page, so the request panel and the
 * country recommendation always price the same number of units.
 */
export function ProductQuantityProvider({ children, initial = 1 }: { children: React.ReactNode; initial?: number }) {
  const [quantity, setRawQuantity] = useState(initial);
  const value = useMemo(
    () => ({ quantity, setQuantity: (next: number) => setRawQuantity(Math.max(1, Math.floor(Number(next)) || 1)) }),
    [quantity],
  );
  return <ProductQuantityContext.Provider value={value}>{children}</ProductQuantityContext.Provider>;
}

/** Falls back to local state when a component is rendered outside a product page. */
export function useProductQuantity(fallback = 1): ProductQuantity {
  const shared = useContext(ProductQuantityContext);
  const [local, setLocal] = useState(fallback);
  return shared ?? { quantity: local, setQuantity: (next: number) => setLocal(Math.max(1, Math.floor(Number(next)) || 1)) };
}
