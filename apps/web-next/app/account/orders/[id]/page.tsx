"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getOrderById, type OrderDetail } from "../../../../lib/api";

const statusOrder = [
  "PENDING",
  "CONFIRMED",
  "PURCHASED",
  "IN_TRANSIT",
  "CUSTOMS",
  "LOCAL_DISPATCH",
  "DELIVERED",
  "CANCELLED",
];

export default function OrderDetailsPage() {
  const params = useParams();
  const orderId = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : undefined;
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) return;
    getOrderById(orderId)
      .then(setOrder)
      .catch(() => setError("Unable to load this order. Check your token or backend status."))
      .finally(() => setLoading(false));
  }, [orderId]);

  if (loading) {
    return <div className="empty-state">Loading order information…</div>;
  }

  if (error || !order) {
    return <div className="empty-state">{error || "Order not found."}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="section__header">
        <div>
          <p className="eyebrow">Order details</p>
          <h2>Order #{order.id}</h2>
        </div>
      </div>

      <div className="order-summary">
        <div>
          <strong>Status</strong>
          <span>{order.status}</span>
        </div>
        <div>
          <strong>Total</strong>
          <span>BDT {order.total_bdt}</span>
        </div>
        <div>
          <strong>Advance</strong>
          <span>BDT {order.advance_bdt}</span>
        </div>
        <div>
          <strong>Remaining</strong>
          <span>BDT {order.remaining_bdt}</span>
        </div>
      </div>

      <div className="section__header">
        <div>
          <p className="eyebrow">Items</p>
          <h2>Order contents</h2>
        </div>
      </div>

      <div className="items-grid">
        {order.items?.map((item) => (
          <div key={`${item.variant_id}-${item.product_name}`} className="item-card">
            <div>
              <strong>{item.product_name}</strong>
              <p className="text-sm text-gray-600">Variant: {item.variant_name || item.variant_id}</p>
            </div>
            <div className="text-sm">Qty {item.qty}</div>
          </div>
        ))}
      </div>

      <div className="section__header">
        <div>
          <p className="eyebrow">Timeline</p>
          <h2>Delivery stages</h2>
        </div>
      </div>

      <div className="timeline-card">
        {statusOrder.map((status) => {
          const reached = order.history?.some((entry) => entry.status === status);
          const entry = order.history?.find((item) => item.status === status);
          return (
            <div key={status} className="timeline-step">
              <span className={`timeline-bullet ${reached ? "timeline-bullet--active" : ""}`}></span>
              <div>
                <div className="font-semibold">{status.replace(/_/g, " ")}</div>
                {entry ? <p className="text-sm text-gray-600">{new Date(entry.created_at).toLocaleString()}</p> : <p className="text-sm text-gray-500">Pending</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
