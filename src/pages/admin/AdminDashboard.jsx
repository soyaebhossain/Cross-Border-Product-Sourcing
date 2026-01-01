import Card from "../../components/common/Card.jsx";
import { Link } from "react-router-dom";

// Static placeholder data; replace with API responses later
const kpis = [
  { label: "Total Orders", value: "3,129", sub: "Updated just now", icon: "🛍️", accent: "bg-blue-100 text-blue-700" },
  { label: "Total Products", value: "3,523", sub: "Updated just now", icon: "📦", accent: "bg-emerald-100 text-emerald-700" },
  { label: "Total Revenue", value: "BDT 3,036,519", sub: "Including delivery charges", icon: "🔗", accent: "bg-amber-100 text-amber-700" },
  { label: "Shipping Charge", value: "BDT 1,556,710", sub: "Collected from all orders", icon: "🚚", accent: "bg-sky-100 text-sky-700" },
  { label: "Revenue from book", value: "BDT 1,461,362", sub: "3477 products sold", icon: "📕", accent: "bg-orange-100 text-orange-700" },
  { label: "Revenue from T-shirt", value: "BDT 18,447", sub: "Excluding shipping charge", icon: "👕", accent: "bg-purple-100 text-purple-700" },
];

const dailyRows = Array.from({ length: 10 }).map((_, i) => ({
  sl: i + 1,
  date: `2025-12-${String(31 - i).padStart(2, "0")}`,
  all: 1000 * (i + 1),
  manual: i % 2 ? 400 * i : 0,
  web: 800 * (i + 2),
}));

const itemRevenues = [
  { name: "Book A", revenue: "BDT 8,379", items: 21 },
  { name: "T-Shirt Jagoron", revenue: "BDT 4,850", items: 12 },
  { name: "Combo Pack", revenue: "BDT 368,500", items: 335 },
  { name: "Book Physics + Math", revenue: "BDT 11,900", items: 205 },
  { name: "Biology Book", revenue: "BDT 584,325", items: 1522 },
  { name: "Physics Book", revenue: "BDT 261,200", items: 653 },
  { name: "Formula Book", revenue: "BDT 39,987", items: 473 },
  { name: "Admission Book", revenue: "BDT 72,800", items: 182 },
];

const ordersStage = [
  { label: "Order Placed", count: 464, color: "bg-blue-500" },
  { label: "Out for Delivery", count: 229, color: "bg-emerald-500" },
  { label: "Completed", count: 2436, color: "bg-indigo-500" },
];

const deliveryOptions = [
  { label: "Home Delivery", orders: 2100, products: 2410 },
  { label: "Sundarban Courier", orders: 571, products: 652 },
];

const ordersByType = [
  { label: "Manual Orders", count: 146, color: "bg-orange-400" },
  { label: "Website Orders", count: 2983, color: "bg-blue-600" },
];

const districts = [
  { name: "Bagerhat", orders: 19, products: 21, options: "home, sundarban" },
  { name: "Bandarban", orders: 1, products: 2, options: "home" },
  { name: "Bhola", orders: 14, products: 17, options: "sundarban, home" },
];

export default function AdminDashboard() {
  return (
    <div className="space-y-6">
      <div className="text-center space-y-1">
        <h1 className="text-2xl font-semibold text-slate-900">Admin Dashboard</h1>
        <p className="text-sm text-gray-600">Snapshot of orders, revenue, and delivery performance.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {kpis.map((k) => (
          <Card key={k.label} className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-500">{k.label}</div>
              <div className="text-xl font-semibold text-slate-900">{k.value}</div>
              <div className="text-xs text-gray-500">{k.sub}</div>
            </div>
            <div className={`h-10 w-10 rounded-xl grid place-items-center ${k.accent}`}>{k.icon}</div>
          </Card>
        ))}
      </div>

      <Card className="space-y-3">
        <div className="font-semibold text-slate-900">Daily Revenue (Excl. Shipping)</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left">SL</th>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-right">All Orders</th>
                <th className="px-3 py-2 text-right">Manual Only</th>
                <th className="px-3 py-2 text-right">Website Only</th>
              </tr>
            </thead>
            <tbody>
              {dailyRows.map((r) => (
                <tr key={r.sl} className="border-t text-gray-700">
                  <td className="px-3 py-2">{r.sl}</td>
                  <td className="px-3 py-2">{r.date}</td>
                  <td className="px-3 py-2 text-right">{r.all.toLocaleString()} ৳</td>
                  <td className="px-3 py-2 text-right">{r.manual.toLocaleString()} ৳</td>
                  <td className="px-3 py-2 text-right">{r.web.toLocaleString()} ৳</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="space-y-3">
        <div className="font-semibold text-slate-900">Item Revenues</div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {itemRevenues.map((item) => (
            <div key={item.name} className="rounded-xl border border-gray-200 px-3 py-2 space-y-1">
              <div className="text-sm font-semibold text-slate-900">{item.name}</div>
              <div className="text-lg font-semibold text-slate-900">{item.revenue}</div>
              <div className="text-xs text-gray-500">Items sold: {item.items}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="space-y-3 lg:col-span-2">
          <div className="font-semibold text-slate-900">Orders by Stage</div>
          <div className="flex flex-col gap-2">
            {ordersStage.map((s) => (
              <div key={s.label} className="flex items-center gap-2 text-sm">
                <span className={`h-2 w-2 rounded-full ${s.color}`} />
                <span className="text-gray-700">{s.label}</span>
                <span className="font-semibold text-slate-900">{s.count}</span>
              </div>
            ))}
          </div>
          <div className="h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-blue-500" style={{ width: "60%" }} />
          </div>
        </Card>

        <Card className="space-y-3">
          <div className="font-semibold text-slate-900">Orders by Type</div>
          <div className="space-y-2">
            {ordersByType.map((o) => (
              <div key={o.label} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${o.color}`} />
                  <span>{o.label}</span>
                </div>
                <span className="font-semibold text-slate-900">{o.count}</span>
              </div>
            ))}
          </div>
          <div className="h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-blue-500" style={{ width: "80%" }} />
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="space-y-3 lg:col-span-2">
          <div className="font-semibold text-slate-900">Delivery Options</div>
          <div className="space-y-2">
            {deliveryOptions.map((d) => (
              <div key={d.label} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-700">{d.label}</span>
                  <span className="font-semibold text-slate-900">{d.orders}</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div className="h-2 rounded-full bg-emerald-500" style={{ width: "70%" }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="space-y-3">
          <div className="font-semibold text-slate-900">Orders by District</div>
          <div className="space-y-2 text-sm">
            {districts.map((d) => (
              <div key={d.name} className="rounded-lg border border-gray-200 px-3 py-2">
                <div className="font-semibold text-slate-900">{d.name}</div>
                <div className="text-xs text-gray-500">Orders: {d.orders} • Products: {d.products}</div>
                <div className="text-xs text-gray-500">Options: {d.options}</div>
              </div>
            ))}
            <Link to="/admin" className="text-xs text-slate-700 underline">View full table</Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
