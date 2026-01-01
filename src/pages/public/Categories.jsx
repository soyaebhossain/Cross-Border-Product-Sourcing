import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Card from "../../components/common/Card.jsx";
import { api } from "../../services/api/client.js";
import { endpoints } from "../../services/api/endpoints.js";
import { Link } from "react-router-dom";

const fallbackCategories = [
  { name: "Phones & wearables", description: "Uncommon models, regional variants, accessories" },
  { name: "Laptops & tablets", description: "Ultrabooks, creator laptops, rugged tablets" },
  { name: "PC components", description: "GPU/CPU/RAM/SSD for builds and upgrades" },
  { name: "Networking", description: "Routers, switches, Wi-Fi 6/6E APs, LTE/5G CPE" },
  { name: "Smart home & IoT", description: "Sensors, hubs, smart locks, cameras" },
  { name: "Power & accessories", description: "Power banks, chargers, cables, adapters" },
];

function normalize(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.results)) return payload.results;
  return [];
}

export default function Categories() {
  const [expanded, setExpanded] = useState(null);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["categories"],
    queryFn: async () => {
      const res = await api.get(endpoints.catalog.categories);
      return res.data;
    },
  });

  const categories = normalize(data);
  const list = categories.length ? categories : fallbackCategories;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Categories</h1>
        <p className="text-gray-600 text-sm mt-1">Electronics we can source across CN / SG / TH.</p>
      </div>

      {isError && (
        <Card>
          <div className="text-sm text-amber-700">Could not load categories from API. Showing defaults.</div>
        </Card>
      )}

      {isLoading && !categories.length ? (
        <div className="text-gray-600 text-sm">Loading categories...</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {list.map((c, idx) => {
            const id = c.id ?? c.slug ?? idx;
            const isOpen = expanded === id;
            return (
              <Card
                key={id}
                className="flex flex-col gap-2 hover:-translate-y-0.5 transition"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold text-slate-900">{c.name || "Category"}</div>
                    <div className="text-sm text-gray-600">
                      {c.description || c.slug || "No description"}
                    </div>
                  </div>
                  <button
                    onClick={() => setExpanded(isOpen ? null : id)}
                    className="text-xs font-medium text-slate-600 border border-gray-200 rounded-full px-3 py-1 hover:border-gray-300"
                    aria-expanded={isOpen}
                  >
                    {isOpen ? "Hide" : "Details"}
                  </button>
                </div>

                {isOpen && (
                  <div className="text-sm text-slate-700 space-y-3">
                    {c.slug && (
                      <div className="text-xs text-gray-600">
                        Slug: <span className="font-mono">{c.slug}</span>
                      </div>
                    )}
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Tell us the exact model/quantity and we’ll source it across CN / SG / TH with best route, pricing,
                      and compliance guidance.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {c.slug && (
                        <Link
                          className="text-xs font-medium text-white bg-slate-900 rounded-full px-3 py-1 hover:bg-slate-800"
                          to={`/products?q=${c.slug}`}
                        >
                          Browse products
                        </Link>
                      )}
                      <Link
                        className="text-xs font-medium text-slate-800 bg-slate-100 rounded-full px-3 py-1 hover:bg-slate-200"
                        to={`/quote${c.slug ? `?category=${encodeURIComponent(c.slug)}` : ""}`}
                      >
                        Request sourcing
                      </Link>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
