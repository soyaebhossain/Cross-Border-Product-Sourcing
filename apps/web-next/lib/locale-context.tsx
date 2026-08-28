"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type AppLocale = "en" | "bn";

type LocaleContextValue = {
  locale: AppLocale;
  intlLocale: "en-BD" | "bn-BD";
  setLocale: (locale: AppLocale) => void;
  toggleLocale: () => void;
};

const STORAGE_KEY = "sourceai-locale";
const COOKIE_KEY = "sourceai-locale";
const LocaleContext = createContext<LocaleContextValue | null>(null);

function persistLocale(nextLocale: AppLocale) {
  window.localStorage.setItem(STORAGE_KEY, nextLocale);
  document.cookie = `${COOKIE_KEY}=${nextLocale}; Path=/; Max-Age=31536000; SameSite=Lax`;
  document.documentElement.lang = nextLocale;
}

export function LocaleProvider({
  children,
  initialLocale = "en",
}: {
  children: React.ReactNode;
  initialLocale?: AppLocale;
}) {
  const [locale, setLocaleState] = useState<AppLocale>(initialLocale);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const nextLocale: AppLocale = stored === "bn" || stored === "en"
      ? stored
      : initialLocale;
    setLocaleState(nextLocale);
    persistLocale(nextLocale);
  }, [initialLocale]);

  const setLocale = (nextLocale: AppLocale) => {
    setLocaleState(nextLocale);
    persistLocale(nextLocale);
  };

  const value = useMemo<LocaleContextValue>(() => ({
    locale,
    intlLocale: locale === "bn" ? "bn-BD" : "en-BD",
    setLocale,
    toggleLocale: () => setLocale(locale === "en" ? "bn" : "en"),
  }), [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used within LocaleProvider");
  return context;
}
