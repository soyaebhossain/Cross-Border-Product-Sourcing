import { create } from "zustand";

const LS_KEY = "sourcemarket_auth_v1";
const initialData = (() => {
  const raw = typeof localStorage !== "undefined" ? localStorage.getItem(LS_KEY) : null;
  return raw ? safeParse(raw) : null;
})();

function safeParse(json) {
  try {
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export const useAuthStore = create((set, get) => ({
  user: initialData?.user ?? null,
  accessToken: initialData?.accessToken ?? null,
  refreshToken: initialData?.refreshToken ?? null,
  roles: initialData?.roles ?? [],
  persist() {
    const { user, accessToken, refreshToken, roles } = get();
    localStorage.setItem(
      LS_KEY,
      JSON.stringify({ user, accessToken, refreshToken, roles })
    );
  },

  hydrate() {
    const raw = localStorage.getItem(LS_KEY);
    const data = raw ? safeParse(raw) : null;
    if (!data) return;
    set({
      user: data.user ?? null,
      accessToken: data.accessToken ?? null,
      refreshToken: data.refreshToken ?? null,
      roles: data.roles ?? [],
    });
  },

  setAuth(payload) {
    const next = {
      user: payload.user ?? null,
      accessToken: payload.accessToken ?? null,
      refreshToken: payload.refreshToken ?? null,
      roles: payload.roles ?? [],
    };
    set(next);
    localStorage.setItem(LS_KEY, JSON.stringify(next));
  },

  setAccessToken(token) {
    set((state) => ({ ...state, accessToken: token }));
    get().persist();
  },

  setRefreshToken(token) {
    set((state) => ({ ...state, refreshToken: token }));
    get().persist();
  },

  logout() {
    set({ user: null, accessToken: null, refreshToken: null, roles: [] });
    localStorage.removeItem(LS_KEY);
  },
}));
