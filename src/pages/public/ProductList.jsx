import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";
import Card from "../../components/common/Card.jsx";
import { Link, useSearchParams } from "react-router-dom";

const apiBase =
  (import.meta.env.VITE_API_URL && import.meta.env.VITE_API_URL.replace(/\/$/, "")) ||
  (() => {
    // Fallback: assume backend is on same host at port 8000 if running Vite dev
    if (typeof window === "undefined") return "";
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  })();

const rawImage = (product) =>
  product?.image ||
  product?.image_url ||
  product?.imageUrl ||
  product?.thumbnail ||
  product?.photo ||
  product?.picture ||
  product?.cover_image ||
  product?.cover ||
  (Array.isArray(product?.images) ? product.images[0]?.url || product.images[0] : null);

const resolveImage = (product) => {
  const src = rawImage(product);
  if (!src) return null;
  if (/^https?:\/\//i.test(src) || src.startsWith("//")) return src;
  return `${apiBase}${src.startsWith("/") ? "" : "/"}${src}`;
};

function normalizeProducts(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  if (payload && Array.isArray(payload.data)) return payload.data;
  if (payload && Array.isArray(payload.items)) return payload.items;
  if (payload && Array.isArray(payload.products)) return payload.products;
  return [];
}

export default function ProductList() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["products", q],
    queryFn: async () => {
      const res = await api.get(endpoints.catalog.products, { params: { q } });
      return res.data;
    },
  });

  const products = normalizeProducts(data);

  const handleSearch = (evt) => {
    setParams(evt.target.value ? { q: evt.target.value } : {});
  };

  const suggestions = useMemo(() => {
    if (!products.length || !q.trim()) return [];
    const lower = q.toLowerCase();
    return products
      .filter((p) => (p.name || "").toLowerCase().includes(lower) || (p.model || "").toLowerCase().includes(lower))
      .slice(0, 5);
  }, [products, q]);

  if (isLoading) {
    return <div className="text-gray-600">Loading products...</div>;
  }

  if (isError) {
    return (
      <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-3">
        Failed to load products.
        <div className="mt-2 text-xs text-red-700/70">{error?.message || "Unknown error"}</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between relative">
        <div>
          <h1 className="text-xl font-semibold">Products</h1>
          <p className="text-gray-600 text-sm mt-1">Showing {products.length} items</p>
        </div>
        <div className="w-full sm:w-80 relative">
          <input
            value={q}
            onChange={handleSearch}
            placeholder="Search by name, model or slug"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:border-black focus:outline-none"
          />
          {suggestions.length > 0 && (
            <div className="absolute z-10 mt-1 w-full rounded-xl border border-gray-200 bg-white shadow-lg">
              {suggestions.map((p) => (
                <Link
                  key={p.id}
                  to={`/product/${p.slug}`}
                  className="block px-3 py-2 text-sm hover:bg-gray-50"
                  onClick={() => setParams({ q: p.name })}
                >
                  <div className="font-semibold text-slate-900">{p.name}</div>
                  <div className="text-xs text-gray-600">{p.model || p.slug}</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {products.length === 0 ? (
        <Card>
          <div className="text-gray-600">No products found.</div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {products.map((p, idx) => {
            const image = resolveImage(p);
            const fallbackLetter = (p.name || p.model || "P").slice(0, 1).toUpperCase();

            return (
              <Card key={p.id ?? p.slug ?? idx} className="flex items-center justify-between gap-4 sm:gap-6">
                <div className="flex-1 space-y-1.5">
                  <div className="font-medium text-lg">{p.name ?? p.title ?? "Untitled"}</div>
                  <div className="text-sm text-gray-600">
                    {p.model ? `Model: ${p.model}` : p.category?.name ? `Category: ${p.category.name}` : "No meta"}
                  </div>
                  <div className="text-xs text-gray-500">
                    {p.variants?.length
                      ? `${p.variants.length} variant${p.variants.length > 1 ? "s" : ""}`
                      : "No variants"}
                  </div>
                  <div className="pt-1">
                    <Link className="text-sm text-black underline" to={`/product/${p.slug}`}>
                      View & request quote
                    </Link>
                  </div>
                </div>

                <div className="h-24 w-28 shrink-0 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center text-xl font-semibold text-gray-400">
                  {image ? (
                    <img
                      src={image}
                      alt={p.name || "Product"}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : (
                    <span>{fallbackLetter}</span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
