/** Brand and site facts in one place. Replace the placeholders when decided. */
export const site = {
  brandName: "LINA",
  domain: "[DOMAIN]",
  instagramHandle: "[INSTAGRAM_HANDLE]",
  /** Public origin, no trailing slash. Baked into static pages at build time. */
  url: (process.env.SITE_URL ?? "http://localhost:3000").replace(/\/$/, ""),
  timeZone: "Africa/Dar_es_Salaam",
} as const;
