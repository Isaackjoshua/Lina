import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { localeAlternates } from "@/lib/seo";

const TYPES = [
  "job",
  "internship",
  "scholarship",
  "fellowship",
  "hackathon",
  "grant",
  "conference",
  "competition",
  "training",
] as const;

export async function generateMetadata({ params }: PageProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  return { alternates: localeAlternates(locale) };
}

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale });

  return (
    <>
      <h1 className="text-3xl font-bold text-brand-dark">{t("site.tagline")}</h1>
      <p className="mt-3 text-lg">{t("site.description")}</p>
      <p className="mt-6 rounded-lg border-l-4 border-accent bg-white px-4 py-3">
        {t("home.comingSoon")}
      </p>

      <h2 className="mt-10 text-xl font-semibold">{t("home.categories")}</h2>
      <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {TYPES.map((type) => (
          <li key={type} className="rounded-lg border border-line bg-white px-4 py-3 font-medium">
            {t(`types.${type}`)}
          </li>
        ))}
      </ul>
    </>
  );
}
