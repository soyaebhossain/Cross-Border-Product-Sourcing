"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMyOrders, type OrderSummary } from "../../../lib/api";

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyOrders()
      .then((data) => setOrders(data))
      .catch(() => setError("Please sign in to view your orders."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="empty-state">Loading your orders…</div>
      ) : error ? (
        <div className="empty-state">{error}</div>
      ) : orders.length === 0 ? (
        <div className="empty-state">
          <strong>No orders yet.</strong>
          <p>Submit a quote and place an order to see it here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <div key={order.id} className="order-card">
              <div className="order-card__row">
                <div>
                  <div className="font-semibold">Order #{order.id}</div>
                  <div className="text-sm text-gray-600">{order.status}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold">BDT {order.total_bdt}</div>
                  <Link className="nav-link" href={`/account/orders/${order.id}`}>
                    View details
                  </Link>
                </div>
              </div>
              <div className="order-card__meta">
                <span>Advance {order.advance_bdt}</span>
                <span>Remaining {order.remaining_bdt}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
