import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Compare Sourcing Options",
  description: "Compare selected products by price, origin, delivery, supplier reliability, and risk.",
  path: "/compare",
  noIndex: true,
});

export default function CompareLayout({ children }: { children: React.ReactNode }) {
  return children;
}
