import { useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Card from "../../components/common/Card.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";

const statusFlow = [
  "PENDING",
  "CONFIRMED",
  "PURCHASED",
  "IN_TRANSIT",
  "CUSTOMS",
  "LOCAL_DISPATCH",
  "DELIVERED",
];

const labels = {
  PENDING: "Pending",
  CONFIRMED: "Confirmed",
  PURCHASED: "Purchased",
  IN_TRANSIT: "In transit",
  CUSTOMS: "Customs",
  LOCAL_DISPATCH: "Local dispatch",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
};

function formatBDT(value) {
  if (value === undefined || value === null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return new Intl.NumberFormat("en-BD", { maximumFractionDigits: 0 }).format(num) + " BDT";
}

export default function OrderDetails() {
  const { id } = useParams();

  const { data, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: async () => {
      const res = await api.get(endpoints.orders.orderById(id));
      return res.data;
    },
  });

  const timeline = useMemo(() => {
    if (!data?.history) return [];
    return statusFlow.map((key) => {
      const hit = data.history.find((h) => h.status === key);
      return { key, label: labels[key] || key, at: hit?.created_at, note: hit?.note };
    });
  }, [data?.history]);

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xl font-bold">Order #{data?.id}</div>
            <div className="text-sm text-gray-600">Status: {data?.status}</div>
            <div className="text-sm text-gray-600">
              Total {formatBDT(data?.total_bdt)} • Advance {formatBDT(data?.advance_bdt)} • Remaining{" "}
              {formatBDT(data?.remaining_bdt)}
            </div>
          </div>
          <Link
            to={`/account/orders/${data?.id}/invoice`}
            className="text-sm font-medium rounded-lg border border-gray-200 px-3 py-2 hover:bg-gray-50"
          >
            Invoice / Download
          </Link>
        </div>
      </Card>

      <Card className="space-y-2">
        <div className="font-semibold">Items</div>
        <div className="space-y-2">
          {(data?.items || []).map((item, idx) => (
            <div key={idx} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
              <div>
                <div className="font-semibold text-sm">
                  {item.product_name || "Product"} • {item.variant_name || "Variant"}
                </div>
                <div className="text-xs text-gray-600">Variant ID: {item.variant_id}</div>
              </div>
              <div className="text-sm text-gray-700">Qty {item.qty}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="space-y-2">
        <div className="font-semibold">Payment</div>
        {data?.manual_payment ? (
          <div className="text-sm text-gray-700 space-y-1">
            <div>Channel: {data.manual_payment.channel}</div>
            <div>Transaction ID: {data.manual_payment.trx_id}</div>
            <div>
              Status: {data.manual_payment.verified ? "Verified" : "Pending verify"}
              {data.manual_payment.verified_at ? ` @ ${new Date(data.manual_payment.verified_at).toLocaleString()}` : ""}
            </div>
            {data.manual_payment.screenshot_url && (
              <a className="text-blue-600 underline" href={data.manual_payment.screenshot_url} target="_blank" rel="noreferrer">
                Screenshot
              </a>
            )}
          </div>
        ) : (
          <div className="text-sm text-gray-600">No manual payment uploaded.</div>
        )}
      </Card>

      <Card className="space-y-3">
        <div className="font-semibold">Timeline</div>
        <div className="space-y-2">
          {timeline.map((step) => (
            <div key={step.key} className="flex items-start gap-3">
              <div
                className={`h-3 w-3 mt-1 rounded-full ${
                  data?.status === step.key || step.at ? "bg-emerald-600" : "bg-gray-300"
                }`}
              />
              <div className="flex-1">
                <div className="font-semibold text-sm">{step.label}</div>
                {step.at && (
                  <div className="text-xs text-gray-500">
                    {new Date(step.at).toLocaleString()} {step.note ? `• ${step.note}` : ""}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="space-y-2">
        <div className="font-semibold">Shipment events</div>
        <div className="space-y-1">
          {data?.shipment?.events?.length ? (
            data.shipment.events.map((evt, idx) => (
              <div key={idx} className="text-sm text-gray-700 flex justify-between">
                <span>{evt.status}</span>
                <span className="text-gray-500">{new Date(evt.created_at).toLocaleString()}</span>
              </div>
            ))
          ) : (
            <div className="text-sm text-gray-600">No shipment updates yet.</div>
          )}
        </div>
        {data?.shipment?.tracking_number && (
          <div className="text-sm text-gray-600">Tracking: {data.shipment.tracking_number}</div>
        )}
      </Card>
    </div>
  );
}
