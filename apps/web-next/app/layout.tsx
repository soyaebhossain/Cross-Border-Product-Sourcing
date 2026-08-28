import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import "./professional.css";
import "./ui-polish.css";
import "./sourcing-basket.css";
import "./header-layout.css";
import "./account-profile.css";
import "./account-saved-quotes.css";
import { Header } from "./Header";
import { Footer } from "./Footer";
import { LocaleProvider, type AppLocale } from "../lib/locale-context";
import { SourcingBasketProvider } from "../lib/sourcing-basket";
import { SITE_NAME, SITE_URL } from "../lib/site-metadata";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "SourceAI | Explainable Sourcing Decision Support",
    template: `%s | ${SITE_NAME}`,
  },
  description: "Compare product cost, supplier reliability, delivery, and sourcing risk before requesting a cross-border quotation.",
  applicationName: SITE_NAME,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: SITE_NAME,
    title: "SourceAI | Explainable Sourcing Decision Support",
    description: "Compare landed cost, supplier reliability, delivery time, and sourcing risk before you order.",
  },
  twitter: {
    card: "summary",
    title: "SourceAI | Explainable Sourcing Decision Support",
    description: "Compare landed cost, supplier reliability, delivery time, and sourcing risk before you order.",
  },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const localeCookie = (await cookies()).get("sourceai-locale")?.value;
  const initialLocale: AppLocale = localeCookie === "bn" ? "bn" : "en";

  return (
    <html lang={initialLocale}>
      <body>
        <LocaleProvider initialLocale={initialLocale}>
          <SourcingBasketProvider>
            <Header />
            {children}
            <Footer />
          </SourcingBasketProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
