/**
 * Decides whether a GitHub account may enter /admin.
 *
 * Called twice: when GitHub sends the user back after login, and again on
 * every admin page load (so changing ADMIN_GITHUB_USERNAME locks out an old
 * session). Must be pure: no env reads, no network.
 *
 * @param login    the GitHub username from the OAuth profile, if any
 * @param allowed  the value of ADMIN_GITHUB_USERNAME, if set
 */
export function isAllowedAdmin(login: string | null | undefined, allowed: string | undefined): boolean {
  // GitHub usernames are case-insensitive, and a stray space in .env should not lock the owner out.
  const expected = allowed?.trim().toLowerCase();
  // No configured admin, or no login: nobody gets in.
  if (!expected || !login) return false;
  return login.toLowerCase() === expected;
}
