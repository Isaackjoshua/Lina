import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { site } from "@/lib/site";
import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "site" });
  return {
    metadataBase: new URL(site.url),
    title: {
      default: `${site.brandName} — ${t("tagline")}`,
      template: `%s | ${site.brandName}`,
    },
    description: t("description"),
  };
}

export default async function LocaleLayout({
  children,
  params,
}: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const t = await getTranslations({ locale });
  const other = locale === "sw" ? "en" : "sw";

  return (
    <html lang={locale}>
      <body className="flex min-h-dvh flex-col antialiased">
        {/* Gives next-intl's links the current locale. messages={null} keeps
            translations out of the browser bundle: all text is rendered on the server. */}
        <NextIntlClientProvider locale={locale} messages={null}>
          <header className="bg-brand text-white">
            <div className="mx-auto flex w-full max-w-3xl items-center justify-between px-4 py-3">
              <Link href="/" className="text-xl font-bold tracking-wide">
                {site.brandName}
              </Link>
              <Suspense
                fallback={
                  <Link
                    href="/"
                    locale={other}
                    className="underline underline-offset-4"
                  >
                    {t("common.switchLanguage")}
                  </Link>
                }
              >
                <LocaleSwitcher to={other} label={t("common.switchLanguage")} />
              </Suspense>
            </div>
          </header>
          <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">
            {children}
          </main>
          <footer className="border-t border-line">
            <p className="mx-auto w-full max-w-3xl px-4 py-6 text-sm text-muted">
              {site.brandName} · {t("site.free")}
            </p>
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
