import { Outlet, Link, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useAuthStore } from "../../store/auth.store.js";

export function PublicLayout() {
  const navigate = useNavigate();
  const auth = useAuthStore();
  const [search, setSearch] = useState("");
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");

  const submitSearch = (e) => {
    e.preventDefault();
    navigate(search ? `/products?q=${encodeURIComponent(search)}` : "/products");
  };

  const userLabel = auth.user?.username || auth.user?.email || auth.user?.phone || "Account";
  const userInitial = userLabel?.[0]?.toUpperCase() || "A";

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("theme-dark");
    } else {
      root.classList.remove("theme-dark");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white/95 backdrop-blur border-b w-full sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-3 md:flex-row md:items-center md:gap-4">
          <div className="flex items-center justify-between gap-3">
            <Link to="/" className="font-bold text-lg whitespace-nowrap">SourceMarket</Link>
            <div className="flex items-center gap-2 md:hidden">
              <button
                onClick={toggleTheme}
                className="rounded-full border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50 whitespace-nowrap theme-toggle"
              >
                {theme === "dark" ? "☀️" : "🌙"}
              </button>
              <Link
                to={auth.accessToken ? "/account/orders" : "/login"}
                className="flex items-center gap-2 text-sm rounded-full border border-gray-200 px-3 py-2 hover:bg-gray-50 whitespace-nowrap account-link"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-white text-xs font-semibold">
                  {userInitial}
                </span>
              </Link>
            </div>
          </div>

          <nav className="flex gap-4 text-sm whitespace-nowrap">
            <Link to="/products" className="hover:underline">Products</Link>
            <Link to="/categories" className="hover:underline">Categories</Link>
            <Link to="/how-it-works" className="hover:underline">How it works</Link>
          </nav>

          <div className="flex flex-col w-full md:flex-1 md:flex-row md:items-center md:justify-end gap-3">
            <form onSubmit={submitSearch} className="flex-1 flex justify-end">
              <div className="relative w-full sm:w-96">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search products or model..."
                  className="w-full rounded-full border border-gray-200 pl-8 pr-4 py-2 text-sm focus:border-black focus:outline-none"
                />
              </div>
            </form>

            <div className="hidden md:flex items-center gap-2">
              <button
                onClick={toggleTheme}
                className="rounded-full border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50 whitespace-nowrap theme-toggle"
              >
                {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
              </button>
              <Link
                to={auth.accessToken ? "/account/orders" : "/login"}
                className="flex items-center gap-2 text-sm rounded-full border border-gray-200 px-3 py-2 hover:bg-gray-50 whitespace-nowrap account-link"
              >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-white text-xs font-semibold">
              {userInitial}
            </span>
            <span className="hidden sm:inline">Login</span>
          </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl w-full mx-auto px-4 py-6 flex-1">
        <Outlet />
      </main>

      <footer className="border-t bg-white w-full mt-auto">
        <div className="max-w-6xl mx-auto px-4 py-6 text-sm text-gray-600 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <span>© {new Date().getFullYear()} SourceMarket</span>
            <span className="hidden md:inline text-gray-400">•</span>
            <div className="flex items-center gap-2">
              <Link className="text-gray-500 hover:text-black" to="/privacy">Privacy</Link>
              <span className="text-gray-300">/</span>
              <Link className="text-gray-500 hover:text-black" to="/terms">Terms</Link>
              <span className="text-gray-300">/</span>
              <Link className="text-gray-500 hover:text-black" to="/cookies">Cookies</Link>
            </div>
          </div>
          <div className="flex items-center gap-3 text-gray-500">
            <a className="hover:text-black" href="#" aria-label="Twitter">𝕏</a>
            <a className="hover:text-black" href="#" aria-label="Facebook">f</a>
            <a className="hover:text-black" href="#" aria-label="Instagram">⌾</a>
            <a className="hover:text-black" href="#" aria-label="LinkedIn">in</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
