import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// Locale-aware Link, redirect and usePathname. Use these instead of next/link
// for public pages so links keep the current language.
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);
