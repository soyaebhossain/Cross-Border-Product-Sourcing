import { cookies } from "next/headers";
import type { AppLocale } from "./locale-context";

/** The language the visitor chose, read from the same cookie the root layout uses. */
export async function getServerLocale(): Promise<AppLocale> {
  return (await cookies()).get("sourceai-locale")?.value === "bn" ? "bn" : "en";
}

/** Country name in the visitor's language, falling back to the catalog's own name. */
export function countryName(code: string, fallback: string, locale: AppLocale): string {
  if (locale !== "bn") return fallback;
  try {
    return new Intl.DisplayNames(["bn"], { type: "region" }).of(code.toUpperCase()) || fallback;
  } catch {
    return fallback;
  }
}
