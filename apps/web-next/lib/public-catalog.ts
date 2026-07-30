import snapshotJson from "../data/public-catalog.snapshot.json";
import type {
  Category,
  Country,
  Product,
  ProductPage,
} from "./api";

export type CatalogBrowseInput = {
  q?: string;
  category?: string;
  page?: number;
  pageSize?: number;
  sort?: string;
  country?: string;
  maxPrice?: number;
  maxDelivery?: number;
  minRating?: number;
  risk?: string;
};

type PublicCatalogSnapshot = {
  schema_version: number;
  counts: {
    categories: number;
    countries: number;
    products: number;
    variants: number;
  };
  categories: Category[];
  countries: Country[];
  products: Product[];
};

const snapshot = snapshotJson as PublicCatalogSnapshot;

function snapshotProduct(product: Product): Product {
  return { ...product, catalog_source: "snapshot" };
}

function normalized(value: string | null | undefined) {
  return (value || "").trim().toLocaleLowerCase();
}

function matchesSearch(product: Product, query: string) {
  if (!query) return true;
  return [
    product.name,
    product.model,
    product.slug,
    product.category.name,
    product.category.slug,
  ].some(value => normalized(value).includes(query));
}

export function getSnapshotProducts(query = ""): Product[] {
  const search = normalized(query);
  return snapshot.products
    .filter(product => matchesSearch(product, search))
    .map(snapshotProduct);
}

export function browseSnapshotProducts(input: CatalogBrowseInput): ProductPage {
  const search = normalized(input.q);
  const category = normalized(input.category);
  const country = normalized(input.country).toUpperCase();
  const risk = normalized(input.risk);
  const page = Math.max(1, input.page || 1);
  const pageSize = Math.min(60, Math.max(1, input.pageSize || 24));
  const sort = input.sort || "name";

  const products = snapshot.products.filter(product => {
    const market = product.market || {};
    const price = market.min_price;
    const rating = market.max_rating || 0;
    const delivery = market.min_delivery_days;
    return (
      matchesSearch(product, search)
      && (!category || normalized(product.category.slug) === category)
      && (!country || (market.countries || []).includes(country))
      && (input.maxPrice === undefined || (price !== undefined && price <= input.maxPrice))
      && (input.maxDelivery === undefined || (delivery !== undefined && delivery <= input.maxDelivery))
      && (input.minRating === undefined || rating >= input.minRating)
      && (!risk || normalized(market.risk_level) === risk)
    );
  });

  products.sort((left, right) => {
    const leftMarket = left.market || {};
    const rightMarket = right.market || {};
    if (sort === "name_desc") return right.name.localeCompare(left.name);
    if (sort === "cheapest") {
      return (leftMarket.min_price ?? Number.POSITIVE_INFINITY)
        - (rightMarket.min_price ?? Number.POSITIVE_INFINITY);
    }
    if (sort === "fastest") {
      return (leftMarket.min_delivery_days ?? Number.POSITIVE_INFINITY)
        - (rightMarket.min_delivery_days ?? Number.POSITIVE_INFINITY);
    }
    if (sort === "highest_rated") {
      return (rightMarket.max_rating || 0) - (leftMarket.max_rating || 0);
    }
    if (sort === "recommended") {
      return (rightMarket.recommended_score || 0)
        - (leftMarket.recommended_score || 0);
    }
    return left.name.localeCompare(right.name);
  });

  const total = products.length;
  const start = (page - 1) * pageSize;
  return {
    items: products.slice(start, start + pageSize).map(snapshotProduct),
    total,
    page,
    page_size: pageSize,
    pages: Math.max(1, Math.ceil(total / pageSize)),
    catalog_source: "snapshot",
  };
}

export function getSnapshotCategories(): Category[] {
  return snapshot.categories;
}

export function getSnapshotCountries(): Country[] {
  return snapshot.countries;
}

export function getSnapshotProductBySlug(slug: string): Product {
  const product = snapshot.products.find(item => item.slug === slug);
  if (!product) throw new Error("Product not found");
  return snapshotProduct(product);
}

export function getSnapshotCounts() {
  return snapshot.counts;
}
