import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

// Sends "/" and any un-prefixed public path to its "/sw/..." or "/en/..." URL.
export default createMiddleware(routing);

export const config = {
  // Public pages only. /admin and /api are not localized; skip Next internals and files.
  matcher: "/((?!api|admin|_next|_vercel|.*\\..*).*)",
};
