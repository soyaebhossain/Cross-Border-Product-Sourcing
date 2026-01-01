import { Outlet, Link } from "react-router-dom";

export function AccountLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white/95 backdrop-blur border-b sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link to="/" className="font-bold text-lg whitespace-nowrap text-slate-900">SourceMarket</Link>
          <nav className="flex items-center gap-3 text-sm text-slate-700">
            <Link to="/products" className="hover:underline">Products</Link>
            <Link to="/categories" className="hover:underline">Categories</Link>
            <Link to="/how-it-works" className="hover:underline">How it works</Link>
          </nav>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <Link to="/account/orders" className="rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50">Account</Link>
            <Link to="/" className="rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50">Home</Link>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 md:grid-cols-4 gap-6">
        <aside className="bg-white border rounded-2xl p-4 md:col-span-1">
          <div className="font-semibold mb-3">My Account</div>
          <div className="flex flex-col gap-2 text-sm">
            <Link to="/account/orders" className="hover:underline">Orders</Link>
            <Link to="/account/saved-quotes" className="hover:underline">Saved Quotes</Link>
          </div>
        </aside>
        <section className="md:col-span-3">
          <Outlet />
        </section>
      </div>
    </div>
  );
}
