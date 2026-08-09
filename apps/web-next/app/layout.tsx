import type { Metadata } from "next";
import "./globals.css";
import "./professional.css";
import "./ui-polish.css";
import "./sourcing-basket.css";
import { Header } from "./Header";
import { Footer } from "./Footer";
import { LocaleProvider } from "../lib/locale-context";
import { SourcingBasketProvider } from "../lib/sourcing-basket";

export const metadata: Metadata = {
  title: "SourceAI | Explainable Sourcing Decision Support",
  description: "Compare product cost, supplier reliability, delivery, and sourcing risk before requesting a cross-border quotation.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <LocaleProvider>
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
