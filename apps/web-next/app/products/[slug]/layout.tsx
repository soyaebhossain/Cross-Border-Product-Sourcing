import type { Metadata } from "next";
import { getProductBySlug } from "../../../lib/api";
import { pageMetadata, SITE_NAME } from "../../../lib/site-metadata";

type ProductLayoutProps = {
  children: React.ReactNode;
  params: Promise<{ slug: string }>;
};

function readableSlug(slug: string) {
  return slug
    .split("-")
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export async function generateMetadata({ params }: Pick<ProductLayoutProps, "params">): Promise<Metadata> {
  const { slug } = await params;
  const canonicalPath = `/products/${encodeURIComponent(slug)}`;

  try {
    const product = await getProductBySlug(slug);
    const metadata = pageMetadata({
      title: product.name,
      description: product.description?.trim()
        || `Compare sourcing options, supplier availability, delivery, and risk for ${product.name}.`,
      path: canonicalPath,
    });
    return { ...metadata, title: { absolute: `${product.name} | ${SITE_NAME}` } };
  } catch {
    const title = readableSlug(slug) || "Product details";
    const metadata = pageMetadata({
      title,
      description: "Review product specifications, sourcing options, delivery, and supplier risk.",
      path: canonicalPath,
      noIndex: true,
    });
    return { ...metadata, title: { absolute: `${title} | ${SITE_NAME}` } };
  }
}

export default function ProductLayout({ children }: ProductLayoutProps) {
  return children;
}
