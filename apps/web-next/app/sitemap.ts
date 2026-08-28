import type { MetadataRoute } from "next";
import { SITE_URL } from "../lib/site-metadata";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    { url: SITE_URL, lastModified, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/products`, lastModified, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/categories`, lastModified, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/quote`, lastModified, changeFrequency: "weekly", priority: 0.7 },
  ];
}
