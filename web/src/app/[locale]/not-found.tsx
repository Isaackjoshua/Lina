import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <>
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <p className="mt-4">
        <Link href="/" className="text-brand underline">
          {t("back")}
        </Link>
      </p>
    </>
  );
}
