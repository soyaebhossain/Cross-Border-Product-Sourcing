import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Global Product Catalog",
  description: "Browse products and compare supplier price, delivery time, reliability, and sourcing risk.",
  path: "/products",
});

export default function ProductsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
