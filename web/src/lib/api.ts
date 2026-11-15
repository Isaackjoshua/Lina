import "server-only";

/**
 * Calls the FastAPI backend's /internal routes from the Next.js server.
 * Only call this after getAdmin() has confirmed the admin: the token proves
 * the request comes from our web server, not who the user is.
 */
export async function internalApi<T>(path: string, init?: RequestInit): Promise<T> {
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const response = await fetch(`${base}/internal${path}`, {
    ...init,
    headers: { ...init?.headers, Authorization: `Bearer ${process.env.INTERNAL_API_TOKEN ?? ""}` },
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error(`API ${path} responded ${response.status}`);
  return (await response.json()) as T;
}
