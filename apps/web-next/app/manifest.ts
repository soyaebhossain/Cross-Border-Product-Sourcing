import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SourceAI – Explainable Sourcing Decision Support",
    short_name: "SourceAI",
    description: "Compare landed cost, supplier reliability, delivery time, and sourcing risk.",
    start_url: "/",
    display: "standalone",
    background_color: "#f5f8fd",
    theme_color: "#0f2b59",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
