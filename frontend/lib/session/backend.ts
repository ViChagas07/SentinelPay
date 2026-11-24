import {
  CSRF_COOKIE,
  CSRF_HEADER,
  REFRESH_COOKIE,
  SESSION_CSRF_COOKIE,
  SESSION_REFRESH_COOKIE,
  type LoginErrorCode,
} from "./constants";
import { ApiError } from "@/lib/api/errors";
import type { CookieReader } from "./cookies";

export type BackendSession = {
  accessToken: string;
  expiresInSeconds: number;
  user: unknown;
};

export type RefreshOutcome =
  | { kind: "refreshed"; session: BackendSession; setCookies: string[] }
  | { kind: "missing" }
  | { kind: "failed"; code: string; status: number; setCookies: string[] };

export type TicketOutcome =
  | { kind: "refreshed"; session: BackendSession; setCookies: string[] }
  | { kind: "failed"; code: string; status: number; setCookies: string[] };

export function readSetCookies(headers: Headers): string[] {
  const getSetCookie = (headers as Headers & { getSetCookie?: () => string[] }).getSetCookie;

  if (typeof getSetCookie === "function") {
    const values = getSetCookie.call(headers);
    return Array.isArray(values) ? values : [];
  }

  const combined = headers.get("set-cookie");
  return combined ? [combined] : [];
}

export function buildCsrfHeaders(cookies: CookieReader): Headers {
  const headers = new Headers();
  const csrf = buildCsrfHeader(cookies);

  if (csrf) {
    headers.set(CSRF_HEADER, csrf);
  }

  return headers;
}
export function buildForwardCookies(cookies: CookieReader): string {
  const pairs: string[] = [];
  const refresh = cookies.get(SESSION_REFRESH_COOKIE)?.value ?? cookies.get(REFRESH_COOKIE)?.value;
  const csrf = cookies.get(SESSION_CSRF_COOKIE)?.value ?? cookies.get(CSRF_COOKIE)?.value;

  if (refresh) {
    pairs.push(`${REFRESH_COOKIE}=${refresh}`);
  }

  if (csrf) {
    pairs.push(`${CSRF_COOKIE}=${csrf}`);
  }

  return pairs.join("; ");
}

export function buildCsrfHeader(cookies: CookieReader): string | null {
  return cookies.get(SESSION_CSRF_COOKIE)?.value ?? cookies.get(CSRF_COOKIE)?.value ?? null;
}

export function extractCookieValue(setCookies: readonly string[], name: string): string | null {
  for (const cookie of setCookies) {
    const [pair] = cookie.split(";");
    const separator = pair?.indexOf("=") ?? -1;

    if (separator < 0 || !pair) {
      continue;
    }

    const cookieName = pair.slice(0, separator).trim();

    if (cookieName !== name) {
      continue;
    }

    const value = pair.slice(separator + 1).trim();
    return value.length > 0 ? value : null;
  }

  return null;
}

export async function requestRefresh(options: {
  cookies: CookieReader;
  backendUrl: string;
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
}): Promise<RefreshOutcome> {
  const refresh =
    options.cookies.get(SESSION_REFRESH_COOKIE)?.value ??
    options.cookies.get(REFRESH_COOKIE)?.value;
  const csrf = buildCsrfHeader(options.cookies);

  if (!refresh || !csrf) {
    return { kind: "missing" };
  }

  const doFetch = options.fetchImpl ?? fetch;
  let response: Response;

  try {
    response = await doFetch(options.backendUrl, {
      method: "POST",
      headers: {
        Accept: "application/json",
        [CSRF_HEADER]: csrf,
        Cookie: buildForwardCookies(options.cookies),
      },
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    return { kind: "failed", code: "network_error", status: 502, setCookies: [] };
  }

  const setCookies = readSetCookies(response.headers);

  if (!response.ok) {
    return {
      kind: "failed",
      code: await readErrorCode(response),
      status: response.status,
      setCookies,
    };
  }

  try {
    const payload = (await response.json()) as {
      access_token?: unknown;
      expires_in?: unknown;
      user?: unknown;
    };

    if (typeof payload.access_token !== "string" || payload.access_token.length === 0) {
      return { kind: "failed", code: "invalid_response", status: 502, setCookies };
    }

    const expiresIn =
      typeof payload.expires_in === "number" && Number.isFinite(payload.expires_in)
        ? payload.expires_in
        : 900;

    return {
      kind: "refreshed",
      session: {
        accessToken: payload.access_token,
        expiresInSeconds: expiresIn,
        user: payload.user,
      },
      setCookies,
    };
  } catch {
    return { kind: "failed", code: "invalid_response", status: 502, setCookies };
  }
}

function parseSessionPayload(payload: unknown): BackendSession | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }

  const record = payload as {
    access_token?: unknown;
    expires_in?: unknown;
    user?: unknown;
  };

  if (typeof record.access_token !== "string" || record.access_token.length === 0) {
    return null;
  }

  const expiresIn =
    typeof record.expires_in === "number" && Number.isFinite(record.expires_in)
      ? record.expires_in
      : 900;

  return {
    accessToken: record.access_token,
    expiresInSeconds: expiresIn,
    user: record.user,
  };
}

export async function requestTicketExchange(options: {
  ticket: string;
  backendUrl: string;
  clientIp?: string | null;
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
}): Promise<TicketOutcome> {
  const doFetch = options.fetchImpl ?? fetch;
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };

  if (options.clientIp) {
    headers["X-Forwarded-For"] = options.clientIp;
  }

  let response: Response;

  try {
    response = await doFetch(options.backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({ ticket: options.ticket }),
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    return { kind: "failed", code: "network_error", status: 502, setCookies: [] };
  }

  const setCookies = readSetCookies(response.headers);

  if (!response.ok) {
    return {
      kind: "failed",
      code: await readErrorCode(response),
      status: response.status,
      setCookies,
    };
  }

  try {
    const session = parseSessionPayload(await response.json());

    if (!session) {
      return { kind: "failed", code: "invalid_response", status: 502, setCookies };
    }

    return { kind: "refreshed", session, setCookies };
  } catch {
    return { kind: "failed", code: "invalid_response", status: 502, setCookies };
  }
}

export async function readErrorCode(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json();

    if (typeof payload === "object" && payload !== null && "code" in payload) {
      const code = (payload as { code?: unknown }).code;
      return typeof code === "string" ? code : "auth_failed";
    }
  } catch {
    return "auth_failed";
  }

  return "auth_failed";
}

export function toLoginErrorCode(code: string): LoginErrorCode | null {
  switch (code) {
    case "invalid_state":
    case "google_auth_failed":
    case "access_denied":
    case "invalid_ticket":
    case "email_not_verified":
    case "too_many_attempts":
    case "rate_limited":
    case "rate_limit_unavailable":
    case "security_service_unavailable":
    case "auth_not_configured":
    case "csrf_invalid":
    case "network_error":
      return code;
    default:
      return null;
  }
}

export function isApiErrorForSession(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

export function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }

  if (error instanceof Error) {
    return error.name === "AbortError" || error.name === "ResponseAborted";
  }

  return false;
}
