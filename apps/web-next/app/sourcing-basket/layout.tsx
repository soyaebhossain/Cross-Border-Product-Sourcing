import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Sourcing Basket",
  description: "Review selected products and request supplier-backed sourcing quotations.",
  path: "/sourcing-basket",
  noIndex: true,
});

export default function SourcingBasketLayout({ children }: { children: React.ReactNode }) {
  return children;
}
