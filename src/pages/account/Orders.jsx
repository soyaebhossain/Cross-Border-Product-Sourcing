import { useQuery } from "@tanstack/react-query";
import Card from "../../components/common/Card.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";
import { Link, useNavigate } from "react-router-dom";

function formatBDT(value) {
  if (value === undefined || value === null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return new Intl.NumberFormat("en-BD", { maximumFractionDigits: 0 }).format(num) + " BDT";
}

const statusStyles = {
  PENDING: "bg-amber-50 text-amber-700 border-amber-100",
  CONFIRMED: "bg-emerald-50 text-emerald-700 border-emerald-100",
  PURCHASED: "bg-blue-50 text-blue-700 border-blue-100",
  IN_TRANSIT: "bg-sky-50 text-sky-700 border-sky-100",
  CUSTOMS: "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-100",
  LOCAL_DISPATCH: "bg-indigo-50 text-indigo-700 border-indigo-100",
  DELIVERED: "bg-emerald-50 text-emerald-700 border-emerald-100",
  CANCELLED: "bg-rose-50 text-rose-700 border-rose-100",
};

export default function Orders() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["myOrders"],
    queryFn: async () => {
      const res = await api.get(endpoints.orders.myOrders);
      return res.data;
    },
  });

  const orders = data?.results || data || [];
  const pendingCount = orders.filter((o) => o.status === "PENDING").length;
  const totalValue = orders.reduce((sum, o) => sum + (Number(o.total_bdt) || 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 bg-white border border-gray-200 rounded-2xl px-4 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="rounded-full border border-gray-200 px-3 py-1 text-sm hover:bg-gray-50"
          >
            ← Back
          </button>
          <div>
            <div className="text-xl font-semibold">My Orders</div>
            <div className="text-sm text-gray-600">Track status, payments, and delivery.</div>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-3 text-xs">
          <div className="rounded-xl border border-gray-200 px-3 py-2">
            <div className="text-gray-500">Orders</div>
            <div className="font-semibold text-gray-900 text-sm">{orders.length}</div>
          </div>
          <div className="rounded-xl border border-gray-200 px-3 py-2">
            <div className="text-gray-500">Pending</div>
            <div className="font-semibold text-amber-700 text-sm">{pendingCount}</div>
          </div>
          <div className="rounded-xl border border-gray-200 px-3 py-2">
            <div className="text-gray-500">Total value</div>
            <div className="font-semibold text-gray-900 text-sm">{formatBDT(totalValue)}</div>
          </div>
        </div>
      </div>
      {isLoading && <div className="text-sm text-gray-600">Loading...</div>}

      {orders.length === 0 ? (
        <Card>
          <div className="text-gray-600 text-sm">No orders yet.</div>
        </Card>
      ) : (
        <div className="space-y-3">
          {orders.map((o) => (
            <Card key={o.id} className="flex flex-col gap-2 border border-gray-200/70 hover:border-gray-300 transition">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="font-semibold text-slate-900">Order #{o.id}</div>
                    <span
                      className={
                        "text-xs font-semibold rounded-full border px-2 py-0.5 " +
                        (statusStyles[o.status] || "bg-gray-50 text-gray-700 border-gray-200")
                      }
                    >
                      {o.status}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600">
                    Total {formatBDT(o.total_bdt)} • Created {new Date(o.created_at).toLocaleDateString()}
                  </div>
                  <div className="text-xs text-gray-500">
                    Advance {formatBDT(o.advance_bdt)} • Remaining {formatBDT(o.remaining_bdt)}
                  </div>
                </div>
                <Link
                  className="text-sm font-medium rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50"
                  to={`/account/orders/${o.id}`}
                >
                  View details
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
