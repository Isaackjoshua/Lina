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
  // TODO(human): return true only for the configured admin account.
  // Until this is implemented nobody can log in (fails closed).
  void login;
  void allowed;
  return false;
}
