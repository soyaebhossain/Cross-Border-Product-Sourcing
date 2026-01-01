import { useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Card from "../../components/common/Card.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";

function formatBDT(value) {
  if (value === undefined || value === null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return new Intl.NumberFormat("en-BD", { maximumFractionDigits: 0 }).format(num) + " BDT";
}

export default function OrderInvoice() {
  const { id } = useParams();
  const printRef = useRef(null);

  const { data, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: async () => {
      const res = await api.get(endpoints.orders.orderById(id));
      return res.data;
    },
  });

  useEffect(() => {
    // preload print-friendly styles if needed
  }, []);

  const handlePrint = () => {
    if (!data) return;
    window.print();
  };

  if (isLoading) return <div>Loading...</div>;

  const paymentHistory = [];
  if (data?.manual_payment) {
    paymentHistory.push({
      channel: data.manual_payment.channel,
      trx_id: data.manual_payment.trx_id,
      status: data.manual_payment.verified ? "Verified" : "Pending",
      at: data.manual_payment.verified_at || data.manual_payment.created_at,
      screenshot: data.manual_payment.screenshot_url,
    });
  }

  return (
    <div className="space-y-4" ref={printRef}>
      <style>{`
        /* Keep on-screen layout when printing */
        @page { size: auto; margin: 0; }
        @media print {
          body {
            margin: 0 !important;
            padding: 0 !important;
            background: #fff !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          /* Hide everything else entirely so it doesn't take space */
          body > * {
            display: none !important;
          }
          .invoice-sheet {
            display: block !important;
            width: 100% !important;
            max-width: none !important;
            margin: 0 !important;
            box-shadow: none !important;
            border: none !important;
            page-break-inside: avoid;
          }
          .invoice-sheet * {
            page-break-inside: avoid;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
        }
      `}</style>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Invoice</h1>
          <div className="text-sm text-gray-600">Order #{data?.id}</div>
        </div>
        <div className="flex gap-2 print-hidden">
          <button
            onClick={handlePrint}
            className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800"
          >
            Print / Download
          </button>
          <Link
            to={`/account/orders/${id}`}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50"
          >
            Back to order
          </Link>
        </div>
      </div>

      <div
        className="invoice-sheet rounded-2xl border border-gray-200 overflow-hidden shadow-sm bg-white"
        style={{ maxWidth: "210mm", margin: "0 auto" }}
      >
        <div className="bg-sky-500 text-white px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-lg font-bold">SourceMarket</div>
            <div className="text-xs opacity-90">Cross-border sourcing</div>
          </div>
          <div className="text-right text-xs space-y-1">
            <div>Invoice #: {String(data?.id || "").padStart(6, "0")}</div>
            <div>Date: {new Date().toLocaleDateString()}</div>
            <div>Status: {data?.status}</div>
          </div>
        </div>

        <div className="px-6 py-4 grid gap-4 md:grid-cols-2 text-sm text-gray-700">
          <div className="space-y-1">
            <div className="font-semibold text-slate-900">Invoice to</div>
            <div>{data?.billing_name || "Customer"}</div>
            <div>{data?.billing_address || "Address not provided"}</div>
          </div>
          <div className="space-y-1 text-right md:text-left">
            <div className="font-semibold text-slate-900">Order summary</div>
            <div>Order #: {data?.id}</div>
            <div>Advance: {formatBDT(data?.advance_bdt)}</div>
            <div>Remaining: {formatBDT(data?.remaining_bdt)}</div>
          </div>
        </div>

        <div className="px-6 pb-4">
          <div className="overflow-hidden rounded-xl border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-gray-700">
                <tr>
                  <th className="text-left px-3 py-2 w-12">#</th>
                  <th className="text-left px-3 py-2">Product Description</th>
                  <th className="text-right px-3 py-2 w-24">Qty</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items || []).map((item, idx) => (
                  <tr key={idx} className={idx % 2 ? "bg-gray-50/60" : "bg-white"}>
                    <td className="px-3 py-2">{idx + 1}</td>
                    <td className="px-3 py-2">
                      <div className="font-semibold text-slate-900">{item.product_name || "Product"}</div>
                      <div className="text-xs text-gray-600">
                        {item.variant_name || "Variant"} (ID {item.variant_id})
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right">{item.qty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="px-6 grid gap-4 md:grid-cols-[2fr,1fr] pb-6">
          <div className="space-y-2">
            <div className="font-semibold text-slate-900">Additional notes</div>
            <p className="text-sm text-gray-700">
              Ops will verify payment and finalize purchasing. Delivery timelines depend on selected lane and customs.
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 border border-gray-200 p-4 space-y-2 text-sm text-gray-700">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>{formatBDT(data?.total_bdt)}</span>
            </div>
            <div className="flex justify-between">
              <span>Advance paid</span>
              <span>{formatBDT(data?.advance_bdt)}</span>
            </div>
            <div className="flex justify-between font-semibold text-slate-900 border-t pt-2">
              <span>Remaining</span>
              <span>{formatBDT(data?.remaining_bdt)}</span>
            </div>
          </div>
        </div>

        <div className="px-6 pb-6 grid gap-4 md:grid-cols-2 text-sm text-gray-700">
          <div className="rounded-xl border border-gray-200 p-4 space-y-2">
            <div className="font-semibold text-slate-900">Terms</div>
            <p>Advance is non-refundable after purchasing. Remaining due at dispatch/customs release.</p>
          </div>
          <div className="rounded-xl border border-gray-200 p-4 space-y-2">
            <div className="font-semibold text-slate-900">Payment history</div>
            {paymentHistory.length === 0 ? (
              <div className="text-gray-600">No payments recorded.</div>
            ) : (
              <div className="space-y-2">
                {paymentHistory.map((p, idx) => (
                  <div key={idx} className="flex justify-between">
                    <span>
                      {p.channel} • {p.trx_id}
                    </span>
                    <span className="text-gray-500">
                      {p.status}
                      {p.at ? ` @ ${new Date(p.at).toLocaleString()}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="px-6 pb-8">
          <div className="border-t border-dashed border-gray-300 pt-4 text-center text-sm text-gray-600">
            Signature
          </div>
        </div>
      </div>
    </div>
  );
}
