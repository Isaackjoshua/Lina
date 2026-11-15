import type { Metadata } from "next";
import { site } from "@/lib/site";
import "../globals.css";

export const metadata: Metadata = {
  title: `${site.brandName} admin`,
  robots: { index: false, follow: false },
};

// The admin is English-only and sits outside the /sw and /en routes.
export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <html lang="en">
      <body className="antialiased">
        <header className="bg-brand-dark px-4 py-3 text-white">
          <span className="font-bold">{site.brandName}</span> admin
        </header>
        <main className="mx-auto w-full max-w-3xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
