import NextAuth, { type DefaultSession } from "next-auth";
import GitHub from "next-auth/providers/github";
import { connection } from "next/server";
import { isAllowedAdmin } from "@/lib/admin";

declare module "next-auth" {
  interface Session {
    user: { login?: string } & DefaultSession["user"];
  }
}

export const githubConfigured = Boolean(
  process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET,
);

export const { handlers, auth, signIn, signOut } = NextAuth({
  // Reads AUTH_GITHUB_ID / AUTH_GITHUB_SECRET / AUTH_SECRET from the environment.
  providers: [GitHub],
  // Signed cookie, no session table: there is exactly one admin.
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 },
  pages: { signIn: "/admin", error: "/admin" },
  callbacks: {
    signIn({ profile }) {
      return isAllowedAdmin(profile?.login as string | undefined, process.env.ADMIN_GITHUB_USERNAME);
    },
    jwt({ token, profile }) {
      if (profile?.login) token.login = profile.login;
      return token;
    },
    session({ session, token }) {
      session.user.login = token.login as string | undefined;
      return session;
    },
  },
});

/** The signed-in admin's GitHub username, or null. Use at the top of every admin read/write. */
export async function getAdmin(): Promise<string | null> {
  // Marks this as request-time work, so Next.js never tries to prerender a session check.
  await connection();
  const session = await auth();
  const login = session?.user?.login;
  return isAllowedAdmin(login, process.env.ADMIN_GITHUB_USERNAME) ? (login ?? null) : null;
}
