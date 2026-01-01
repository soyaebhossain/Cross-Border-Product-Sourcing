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

export default function SavedQuotes() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["savedQuotes"],
    queryFn: async () => {
      const res = await api.get(endpoints.quote.saved);
      return res.data;
    },
  });

  const quotes = data?.results || data || [];

  return (
    <div className="space-y-4">
      <div className="text-xl font-semibold">Saved Quotes</div>
      {isLoading && <div>Loading...</div>}
      {isError && (
        <Card>
          <div className="text-sm text-red-600">Failed to load saved quotes.</div>
        </Card>
      )}

      {quotes.length === 0 ? (
        <Card>
          <div className="text-sm text-gray-600">No saved quotes yet.</div>
        </Card>
      ) : (
        <div className="space-y-3">
          {quotes.map((q) => (
            <Card key={q.id} className="flex flex-col gap-1">
              <div className="font-semibold">
                {q.product_name || "Product"} — {q.variant_name || "Variant"}
              </div>
              <div className="text-sm text-gray-600">
                {q.qty} pcs • {q.country_id} • {q.mode}
              </div>
              <div className="text-sm text-gray-700">
                Total: {formatBDT(q.response?.breakdown?.total_bdt)} • ETA:{" "}
                {q.response?.eta ? `${q.response.eta.min_days}-${q.response.eta.max_days} days` : "-"}
              </div>
              <div className="text-xs text-gray-500">
                Saved at {q.created_at ? new Date(q.created_at).toLocaleString() : ""}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
