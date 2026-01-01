import { useEffect } from "react";
import { useAuthStore } from "../../store/auth.store.js";

export function AppHydrate({ children }) {
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return children;
}
