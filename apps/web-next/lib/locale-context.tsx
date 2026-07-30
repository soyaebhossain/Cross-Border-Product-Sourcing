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
const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>("en");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const nextLocale: AppLocale = stored === "bn" ? "bn" : "en";
    setLocaleState(nextLocale);
    document.documentElement.lang = nextLocale;
  }, []);

  const setLocale = (nextLocale: AppLocale) => {
    setLocaleState(nextLocale);
    window.localStorage.setItem(STORAGE_KEY, nextLocale);
    document.documentElement.lang = nextLocale;
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
