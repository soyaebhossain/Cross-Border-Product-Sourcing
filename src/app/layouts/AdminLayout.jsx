import { Outlet, Link } from "react-router-dom";

export function AdminLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 md:grid-cols-5 gap-6">
        <aside className="bg-white border rounded-2xl p-4 md:col-span-1">
          <div className="font-semibold mb-3">Admin</div>
          <div className="flex flex-col gap-2 text-sm">
            <Link to="/admin" className="hover:underline">Dashboard</Link>
            <Link to="/admin/offers" className="hover:underline">Offers</Link>
            <Link to="/admin/orders" className="hover:underline">Orders</Link>
            <Link to="/admin/shipments" className="hover:underline">Shipments</Link>
            <Link to="/admin/rules" className="hover:underline">Rules</Link>
          </div>
        </aside>
        <section className="md:col-span-4">
          <Outlet />
        </section>
      </div>
    </div>
  );
}
