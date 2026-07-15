import type { Metadata } from "next";
import "./globals.css";
import "./professional.css";
import { Header } from "./Header";
import { Footer } from "./Footer";

export const metadata: Metadata = {
  title: "SourceAI | AI Decision-Support Marketplace",
  description: "A Decision-Support Marketplace Using Artificial Intelligence for Efficient Cross-Border Product Sourcing.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Header />
        {children}
        <Footer />
      </body>
    </html>
  );
}
