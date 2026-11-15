"use client";

import { Link, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";

/** Links to the same page in the other language. */
export function LocaleSwitcher({ to, label }: { to: Locale; label: string }) {
  const pathname = usePathname();
  return (
    <Link href={pathname} locale={to} hrefLang={to} lang={to} className="underline underline-offset-4">
      {label}
    </Link>
  );
}
