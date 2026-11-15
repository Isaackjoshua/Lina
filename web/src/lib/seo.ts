import { routing } from "@/i18n/routing";
import { site } from "@/lib/site";

/**
 * Canonical + hreflang links for a public page.
 * `path` is the part after the locale, e.g. "" for home or "/about".
 */
export function localeAlternates(locale: string, path = "") {
  const languages: Record<string, string> = {};
  for (const l of routing.locales) languages[l] = `${site.url}/${l}${path}`;
  languages["x-default"] = `${site.url}/${routing.defaultLocale}${path}`;
  return { canonical: `${site.url}/${locale}${path}`, languages };
}
