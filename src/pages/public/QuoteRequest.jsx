import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import Card from "../../components/common/Card.jsx";

export default function QuoteRequest() {
  const [params] = useSearchParams();
  const initialCategory = params.get("category") || params.get("q") || "";

  const [form, setForm] = useState({
    category: initialCategory,
    product: "",
    model: "",
    qty: 1,
    country: "",
    mode: "air",
    delivery: "door",
    notes: "",
    budget: "",
  });

  const [submitted, setSubmitted] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Request sourcing</h1>
        <p className="text-gray-600 text-sm mt-1">
          Share what you need and we’ll source across CN / SG / TH with the best lane, price, and compliance guidance.
        </p>
      </div>

      <Card className="space-y-4">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Category</label>
              <input
                name="category"
                value={form.category}
                onChange={handleChange}
                placeholder="e.g., pc-components"
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Product</label>
              <input
                name="product"
                value={form.product}
                onChange={handleChange}
                placeholder="e.g., NVIDIA RTX 4070, Dyson V12"
                required
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Model / specs</label>
              <input
                name="model"
                value={form.model}
                onChange={handleChange}
                placeholder="e.g., 4070-12G, EU plug, color"
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Quantity</label>
              <input
                type="number"
                min="1"
                name="qty"
                value={form.qty}
                onChange={handleChange}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Destination country</label>
              <input
                name="country"
                value={form.country}
                onChange={handleChange}
                placeholder="e.g., BD, SG, TH"
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Budget (optional)</label>
              <input
                name="budget"
                value={form.budget}
                onChange={handleChange}
                placeholder="e.g., under $900"
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Mode</label>
              <select
                name="mode"
                value={form.mode}
                onChange={handleChange}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black bg-white"
              >
                <option value="air">Air</option>
                <option value="sea">Sea</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-700">Delivery</label>
              <select
                name="delivery"
                value={form.delivery}
                onChange={handleChange}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black bg-white"
              >
                <option value="door">Door</option>
                <option value="pickup">Pickup</option>
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-700">Notes / acceptance criteria</label>
            <textarea
              name="notes"
              value={form.notes}
              onChange={handleChange}
              placeholder="Preferred brands, must-have certifications, target ETA, incoterms, etc."
              rows={3}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-black"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800"
            >
              Submit request
            </button>
            {submitted && <span className="text-xs text-green-700">Saved locally. We’ll wire this to the API next.</span>}
          </div>
        </form>
      </Card>
    </div>
  );
}
