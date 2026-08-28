import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Request a Sourcing Quote",
  description: "Estimate landed cost and compare explainable supplier recommendations for your sourcing request.",
  path: "/quote",
});

export default function QuoteLayout({ children }: { children: React.ReactNode }) {
  return children;
}
