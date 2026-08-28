import { pageMetadata } from "../../lib/site-metadata";

export const metadata = pageMetadata({
  title: "Product Categories",
  description: "Explore SourceAI catalog categories for cross-border product sourcing.",
  path: "/categories",
});

export default function CategoriesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
