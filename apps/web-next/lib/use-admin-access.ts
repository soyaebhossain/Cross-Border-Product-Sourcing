"use client";

import { useEffect, useState } from "react";
import { getCurrentUser } from "./api";

export function useAdminAccess() {
  const [role, setRole] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    getCurrentUser().then(user => {
      if (active) setRole(user.role);
    }).catch(() => {
      if (active) setRole(null);
    });
    return () => { active = false; };
  }, []);
  return { role, isAdmin: role === "admin", loading: role === null };
}
