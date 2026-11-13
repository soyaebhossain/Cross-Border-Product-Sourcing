"use client";

import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createPurchaseOrder } from "../lib/admin-erp-api";
import { useLocale } from "../lib/locale-context";

/** Starts procurement for a confirmed customer order and opens the new purchase order. */
export function RaisePurchaseOrderButton({ orderId, status }: { orderId: number; status: string }) {
  const { locale } = useLocale();
  const bn = locale === "bn";
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!["CONFIRMED", "PURCHASED"].includes(status)) return null;

  const raise = async () => {
    setBusy(true);
    setError("");
    try {
      const created = await createPurchaseOrder(orderId);
      router.push(`/admin/procurement/${created.id}` as Route);
    } catch (reason) {
      // The usual reason is that this order already has a purchase order; the message names it.
      setError(reason instanceof Error ? reason.message : (bn ? "Purchase order তৈরি করা যায়নি।" : "The purchase order could not be created."));
      setBusy(false);
    }
  };

  return <>
    <button className="admin-button admin-button--primary" type="button" disabled={busy} onClick={() => void raise()}>
      {busy ? (bn ? "তৈরি হচ্ছে…" : "Creating…") : (bn ? "সাপ্লায়ার purchase order তৈরি করুন" : "Raise supplier purchase order")}
    </button>
    {error ? <span className="admin-alert admin-alert--error" role="alert">{error}</span> : null}
  </>;
}
