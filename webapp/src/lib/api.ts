/**
 * Thin wrapper around `fetch` that knows where the FastAPI process lives
 * (server-side = INTERNAL_API_BASE; browser-side = same origin).
 */
import { cookies } from "next/headers";

const SESSION_COOKIE = process.env.SESSION_COOKIE_NAME ?? "jyry_session";

function serverBase(): string {
  return process.env.INTERNAL_API_BASE ?? "http://127.0.0.1:8001";
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function serverFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const ck = await cookies();
  const token = ck.get(SESSION_COOKIE)?.value;
  const headers = new Headers(init.headers);
  if (token) headers.set("Cookie", `${SESSION_COOKIE}=${token}`);
  const url = `${serverBase()}${path}`;
  const res = await fetch(url, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function isAuthenticated(): Promise<boolean> {
  const ck = await cookies();
  return Boolean(ck.get(SESSION_COOKIE)?.value);
}
