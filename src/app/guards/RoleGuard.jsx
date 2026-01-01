import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../../store/auth.store.js";

export function RoleGuard({ allow = [] }) {
  const roles = useAuthStore((s) => s.roles);

  const ok = allow.length === 0 || allow.some((r) => roles.includes(r));
  if (!ok) return <Navigate to="/" replace />;
  return <Outlet />;
}
