import type { MetadataRoute } from "next";
import { SITE_URL } from "../lib/site-metadata";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/account/",
        "/admin/",
        "/compare",
        "/forgot-password",
        "/login",
        "/research",
        "/reset-password",
        "/signup",
        "/sourcing-basket",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
