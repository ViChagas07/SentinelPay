import {
  OIDC_NEXT_COOKIE,
  OIDC_NEXT_MAX_AGE_SECONDS,
  SESSION_COOKIE,
  SESSION_COOKIE_MAX_AGE_FALLBACK,
  SESSION_EXP_COOKIE,
  SESSION_MARKER_MAX_AGE_SECONDS,
  SESSION_REFRESH_COOKIE,
} from "./constants";

export type CookieReader = {
  get: (name: string) => { value: string } | undefined;
};

const REFRESH_AHEAD_SECONDS = 30;

export function hasSessionCookie(cookies: CookieReader): boolean {
  return readSessionToken(cookies) !== undefined;
}

export function readSessionToken(cookies: CookieReader): string | undefined {
  const value = cookies.get(SESSION_COOKIE)?.value;
  return value && value.length > 0 ? value : undefined;
}

export function readSessionRefreshToken(cookies: CookieReader): string | undefined {
  const value = cookies.get(SESSION_REFRESH_COOKIE)?.value;
  return value && value.length > 0 ? value : undefined;
}

export function readOidcNext(cookies: CookieReader): string | undefined {
  const value = cookies.get(OIDC_NEXT_COOKIE)?.value;
  return value && value.length > 0 ? value : undefined;
}

export function readSessionExpiry(cookies: CookieReader): number | null {
  const raw = cookies.get(SESSION_EXP_COOKIE)?.value;
  const parsed = raw ? Number(raw) : Number.NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function isSessionExpiring(cookies: CookieReader, now: number = Date.now()): boolean {
  const expiry = readSessionExpiry(cookies);

  if (expiry === null) {
    return true;
  }

  return expiry - REFRESH_AHEAD_SECONDS * 1000 <= now;
}

export type SessionCookieFlags = {
  httpOnly: boolean;
  sameSite: "lax" | "strict" | "none";
  path: string;
  secure: boolean;
  maxAge: number;
};

export function sessionCookieFlags(
  maxAgeSeconds: number,
  secure: boolean,
  path = "/",
): SessionCookieFlags {
  return {
    httpOnly: true,
    sameSite: "lax",
    path,
    secure,
    maxAge: Math.max(1, Math.floor(maxAgeSeconds)),
  };
}

export function oidcNextCookieFlags(secure: boolean): SessionCookieFlags {
  return {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure,
    maxAge: OIDC_NEXT_MAX_AGE_SECONDS,
  };
}

export function expiryCookieFlags(secure: boolean): SessionCookieFlags {
  return {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure,
    maxAge: SESSION_MARKER_MAX_AGE_SECONDS,
  };
}

export function safeSessionMaxAge(expiresInSeconds: number | null | undefined): number {
  if (typeof expiresInSeconds !== "number" || !Number.isFinite(expiresInSeconds)) {
    return SESSION_COOKIE_MAX_AGE_FALLBACK;
  }

  return Math.max(1, Math.floor(expiresInSeconds));
}

export function isSecureRequest(url: string, forwardedProto?: string | null): boolean {
  const forwarded = forwardedProto?.split(",")[0]?.trim().toLowerCase();

  if (forwarded === "https") {
    return true;
  }

  return url.startsWith("https://");
}
