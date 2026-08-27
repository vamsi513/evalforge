import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://evalforge-platform.vercel.app";
  const routes = ["/", "/runs", "/datasets", "/experiments", "/gates"];
  return routes.map(route => ({
    url: `${base}${route}`,
    lastModified: new Date(),
    changeFrequency: "weekly" as const,
    priority: route === "/" ? 1.0 : 0.8,
  }));
}
