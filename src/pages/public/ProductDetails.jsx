import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import Card from "../../components/common/Card.jsx";
import Button from "../../components/common/Button.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";
import { useAuthStore } from "../../store/auth.store.js";

const countryOptions = [
  { code: "CN", name: "China" },
  { code: "SG", name: "Singapore" },
  { code: "TH", name: "Thailand" },
];

const modeOptions = [
  { value: "LOCAL", label: "Local (fast, air)" },
  { value: "BULK", label: "Bulk (sea, cheaper)" },
];

const deliveryOptions = [
  { value: "DOOR", label: "Door delivery" },
  { value: "PICKUP", label: "Pickup" },
];

const paymentChannels = ["bKash", "Nagad", "Rocket", "SSLCommerz"];

function formatBDT(value) {
  if (value === undefined || value === null) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return new Intl.NumberFormat("en-BD", { maximumFractionDigits: 0 }).format(num) + " BDT";
}

export default function ProductDetails() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const auth = useAuthStore();

  const { data: product, isLoading } = useQuery({
    queryKey: ["product", slug],
    queryFn: async () => {
      const res = await api.get(endpoints.catalog.productBySlug(slug));
      return res.data;
    },
  });

  const [form, setForm] = useState({
    variantId: null,
    country: "CN",
    mode: "LOCAL",
    qty: 1,
    delivery_type: "DOOR",
  });
  const [offerId, setOfferId] = useState(null);
  const [payment, setPayment] = useState({ trx_id: "", channel: "bKash", screenshot_url: "" });

  useEffect(() => {
    if (product?.default_variant_id && !form.variantId) {
      setForm((prev) => ({ ...prev, variantId: product.default_variant_id }));
    } else if (product?.variants?.length && !form.variantId) {
      setForm((prev) => ({ ...prev, variantId: product.variants[0].id }));
    }
  }, [product, form.variantId]);

  const quoteMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post(endpoints.quote.create, payload);
      return res.data;
    },
  });

  const saveQuoteMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post(endpoints.quote.save, payload);
      return res.data;
    },
  });

  const orderMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post(endpoints.orders.createManual, payload);
      return res.data;
    },
  });

  const recommendMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post(endpoints.quote.recommend, payload);
      return res.data;
    },
  });

  useEffect(() => {
    const selectedId =
      quoteMutation.data?.selected_offer_id || quoteMutation.data?.offers_top?.[0]?.id || null;
    if (selectedId && !offerId) setOfferId(selectedId);
  }, [quoteMutation.data, offerId]);

  const selectedVariant = useMemo(
    () => product?.variants?.find((v) => v.id === form.variantId),
    [product, form.variantId]
  );

  const handleQuote = async () => {
    if (!form.variantId) return;
    const payload = {
      variant_id: form.variantId,
      country: form.country,
      mode: form.mode,
      qty: Number(form.qty) || 1,
      delivery_type: form.delivery_type,
    };
    await quoteMutation.mutateAsync(payload);
  };

  const handleCreateOrder = async () => {
    if (!auth.accessToken) {
      navigate("/login");
      return;
    }
    if (!quoteMutation.data) {
      await handleQuote();
    }
    if (!payment.trx_id) {
      return;
    }
    const payload = {
      variant_id: form.variantId,
      country: form.country,
      mode: form.mode,
      qty: Number(form.qty) || 1,
      delivery_type: form.delivery_type,
      offer_id: offerId,
      trx_id: payment.trx_id,
      channel: payment.channel,
      screenshot_url: payment.screenshot_url,
    };
    const result = await orderMutation.mutateAsync(payload);
    if (result?.order_id) {
      navigate(`/account/orders/${result.order_id}`);
    }
  };

  const handleSaveQuote = async () => {
    if (!auth.accessToken) {
      navigate("/login");
      return;
    }
    if (!quoteMutation.data || !form.variantId) {
      await handleQuote();
    }
    const payload = {
      variant_id: form.variantId,
      country: form.country,
      mode: form.mode,
      qty: Number(form.qty) || 1,
      delivery_type: form.delivery_type,
      response: quoteMutation.data,
    };
    await saveQuoteMutation.mutateAsync(payload);
  };

  const handleRecommend = async (priority = "balanced") => {
    if (!form.variantId) return;
    await recommendMutation.mutateAsync({
      variant_id: form.variantId,
      qty: Number(form.qty) || 1,
      delivery_type: form.delivery_type,
      priority,
    });
  };

  const offers = quoteMutation.data?.offers_top || [];
  const breakdown = quoteMutation.data?.breakdown;
  const eta = quoteMutation.data?.eta;

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xl font-bold">{product?.name}</div>
            <div className="text-gray-600">{product?.model || ""}</div>
          </div>
          <div className="text-sm text-gray-600">
            Variants: {product?.variants?.length || 0}
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <label className="text-sm font-semibold text-gray-700">Variant</label>
            <select
              value={form.variantId || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, variantId: Number(e.target.value) }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2"
            >
              <option value="" disabled>
                Select a variant
              </option>
              {product?.variants?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.variant_name || v.sku || "Variant"} • {v.weight_kg} kg
                </option>
              ))}
            </select>
            {selectedVariant && (
              <div className="text-xs text-gray-500">
                Dim: {selectedVariant.length_cm}×{selectedVariant.width_cm}×{selectedVariant.height_cm} cm • Weight:{" "}
                {selectedVariant.weight_kg} kg
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Quantity</label>
                <input
                  type="number"
                  min={1}
                  value={form.qty}
                  onChange={(e) => setForm((prev) => ({ ...prev, qty: Number(e.target.value) || 1 }))}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Destination</label>
                <select
                  value={form.country}
                  onChange={(e) => setForm((prev) => ({ ...prev, country: e.target.value }))}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2"
                >
                  {countryOptions.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Mode</label>
                <select
                  value={form.mode}
                  onChange={(e) => setForm((prev) => ({ ...prev, mode: e.target.value }))}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2"
                >
                  {modeOptions.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Delivery</label>
                <select
                  value={form.delivery_type}
                  onChange={(e) => setForm((prev) => ({ ...prev, delivery_type: e.target.value }))}
                  className="w-full rounded-xl border border-gray-200 px-3 py-2"
                >
                  {deliveryOptions.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-3 flex-wrap">
              <Button onClick={handleQuote} disabled={quoteMutation.isPending || !form.variantId}>
                {quoteMutation.isPending ? "Calculating..." : "Get quote"}
              </Button>
              {quoteMutation.data && (
                <Button
                  onClick={handleSaveQuote}
                  disabled={saveQuoteMutation.isPending}
                  className="bg-slate-200 text-slate-900 hover:bg-slate-300"
                >
                  {saveQuoteMutation.isPending ? "Saving..." : "Save quote"}
                </Button>
              )}
              {quoteMutation.data && (
                <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2">
                  ETA {eta?.min_days}-{eta?.max_days} days • Total {formatBDT(breakdown?.total_bdt)}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <div className="text-sm font-semibold text-gray-700">Offers</div>
            <div className="flex flex-wrap gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleRecommend("fast")}
                className="rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50"
              >
                Recommend fastest
              </button>
              <button
                type="button"
                onClick={() => handleRecommend("cheap")}
                className="rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50"
              >
                Recommend cheapest
              </button>
              <button
                type="button"
                onClick={() => handleRecommend("balanced")}
                className="rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50"
              >
                Recommend balanced
              </button>
              {recommendMutation.isPending && <span className="text-gray-500">Loading recommendations…</span>}
            </div>
            {offers.length === 0 ? (
              <Card className="bg-slate-50 text-sm text-gray-600">No offers found for this combination.</Card>
            ) : (
              <div className="space-y-2">
                {offers.map((offer) => (
                  <label
                    key={offer.id}
                    className="flex items-center gap-3 rounded-2xl border border-gray-200 p-3 cursor-pointer hover:border-black"
                  >
                    <input
                      type="radio"
                      name="offer"
                      value={offer.id}
                      checked={offerId === offer.id}
                      onChange={() => setOfferId(offer.id)}
                    />
                    <div className="flex-1">
                      <div className="font-semibold">{offer.seller}</div>
                      <div className="text-sm text-gray-600">
                        {offer.currency} {offer.price_origin} • Stock {offer.stock}
                      </div>
                      <div className="text-xs text-gray-500">MOQ {offer.moq} • Rating {offer.rating}</div>
                    </div>
                  </label>
                ))}
              </div>
            )}

            {recommendMutation.data?.routes?.length ? (
              <Card className="bg-slate-50 space-y-2">
                <div className="font-semibold text-slate-900 text-sm">Suggested lanes</div>
                <div className="space-y-2">
                  {recommendMutation.data.routes.slice(0, 3).map((r, idx) => (
                    <div key={idx} className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2">
                      <div>
                        <div className="font-semibold text-sm text-slate-900">{r.country} • {r.mode}</div>
                        <div className="text-xs text-gray-600">ETA {r.eta.min_days}-{r.eta.max_days} days</div>
                      </div>
                      <div className="text-sm text-slate-900">Total {formatBDT(r.total_bdt)}</div>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-gray-500">Based on priority: {recommendMutation.data.priority}</div>
              </Card>
            ) : null}

            {breakdown && (
              <Card className="bg-slate-50">
                <div className="font-semibold">Quote breakdown</div>
                <div className="text-sm text-gray-600 mt-2 space-y-1">
                  <div className="flex justify-between">
                    <span>Origin</span>
                    <span>{formatBDT(breakdown.origin_price_bdt)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Shipping</span>
                    <span>{formatBDT(breakdown.shipping_bdt)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Duty/VAT est.</span>
                    <span>{formatBDT(breakdown.duty_vat_bdt)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Service fee</span>
                    <span>{formatBDT(breakdown.service_fee_bdt)}</span>
                  </div>
                  <div className="flex justify-between font-semibold border-t pt-2">
                    <span>Total</span>
                    <span>{formatBDT(breakdown.total_bdt)}</span>
                  </div>
                  <div className="flex justify-between text-emerald-700">
                    <span>Advance</span>
                    <span>{formatBDT(breakdown.advance_bdt)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Remaining</span>
                    <span>{formatBDT(breakdown.remaining_bdt)}</span>
                  </div>
                </div>
                {eta && (
                  <div className="text-xs text-gray-500 mt-2">
                    ETA {eta.min_days}-{eta.max_days} days via {form.mode === "LOCAL" ? "air" : "sea"}.
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      </Card>

      <Card className="space-y-3">
        <div className="font-semibold">Confirm order & mark advance paid</div>
        <div className="text-sm text-gray-600">
          Submit the payment reference you used. Ops will verify and move the order to purchasing.
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="space-y-1">
            <label className="text-sm font-semibold text-gray-700">Channel</label>
            <select
              value={payment.channel}
              onChange={(e) => setPayment((prev) => ({ ...prev, channel: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2"
            >
              {paymentChannels.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm font-semibold text-gray-700">Transaction ID</label>
            <input
              value={payment.trx_id}
              onChange={(e) => setPayment((prev) => ({ ...prev, trx_id: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2"
              placeholder="e.g., TXN12345"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-semibold text-gray-700">Screenshot URL (optional)</label>
            <input
              value={payment.screenshot_url}
              onChange={(e) => setPayment((prev) => ({ ...prev, screenshot_url: e.target.value }))}
              className="w-full rounded-xl border border-gray-200 px-3 py-2"
              placeholder="https://..."
            />
          </div>
        </div>

        {!auth.accessToken && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
            Please log in before confirming an order.
          </div>
        )}

        <div className="flex gap-3">
          <Button
            onClick={handleCreateOrder}
            disabled={orderMutation.isPending || !payment.trx_id || !form.variantId}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {orderMutation.isPending ? "Submitting..." : "Confirm order"}
          </Button>
          {orderMutation.isError && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
              Failed to submit order. Please re-check required fields.
            </div>
          )}
        </div>
      </Card>

      <Card className="text-sm text-gray-600">
        <div className="font-semibold text-gray-900 mb-2">What happens next</div>
        <ul className="list-disc list-inside space-y-1">
          <li>Ops verifies your advance payment and confirms stock with the selected seller.</li>
          <li>We purchase, arrange QC and ship. You will see status and shipment events on the order page.</li>
          <li>Remaining payment is due at customs release or local dispatch, depending on the lane.</li>
        </ul>
        <div className="mt-3 text-sm">
          Need help? <Link to="/login" className="underline">Talk to an operator</Link>.
        </div>
      </Card>
    </div>
  );
}
