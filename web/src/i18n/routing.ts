import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["sw", "en"],
  // Swahili first (SPEC §3). "/" always redirects to "/sw"; we do not guess from
  // the browser language, because many Tanzanian phones are set to English.
  defaultLocale: "sw",
  localePrefix: "always",
  localeDetection: false,
});

export type Locale = (typeof routing.locales)[number];
