import type { NextRequest } from "next/server";

import { buildBackendUrl } from "@/lib/api/config";
import { requestRefresh, type RefreshOutcome } from "@/lib/session/backend";
import {
  SESSION_COOKIE,
  SESSION_CSRF_COOKIE,
  SESSION_EXPIRED_CODE,
  SESSION_EXP_COOKIE,
  SESSION_MARKER_MAX_AGE_SECONDS,
  SESSION_REFRESH_COOKIE,
  REFRESH_COOKIE,
  CSRF_COOKIE,
} from "@/lib/session/constants";
import {
  isSecureRequest,
  isSessionExpiring,
  readSessionToken,
  safeSessionMaxAge,
} from "@/lib/session/cookies";
import { extractCookieValue } from "@/lib/session/backend";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "accept-language",
  "content-type",
  "idempotency-key",
  "range",
  "if-none-match",
  "if-modified-since",
];

const FORWARDED_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "cache-control",
  "etag",
  "last-modified",
  "x-request-id",
  "retry-after",
  "content-range",
  "accept-ranges",
];

export type BackendCall = {
  request: NextRequest;
  path: string;
  method: string;
  body?: BodyInit | null;
  accessToken: string;
  signal?: AbortSignal;
};

export type SessionResult = {
  response: Response;
  refreshed: boolean;
  expired: boolean;
};

function buildForwardHeaders(call: BackendCall): Headers {
  const headers = new Headers();

  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = call.request.headers.get(name);

    if (value) {
      headers.set(name, value);
    }
  }

  headers.set("Authorization", `Bearer ${call.accessToken}`);
  headers.set("Accept", headers.get("Accept") ?? "application/json");

  return headers;
}

export async function callBackend(call: BackendCall): Promise<Response> {
  const init: RequestInit & { duplex?: "half" } = {
    method: call.method,
    headers: buildForwardHeaders(call),
    cache: "no-store",
    redirect: "manual",
    signal: call.signal,
  };

  if (call.body !== undefined && call.method !== "GET" && call.method !== "HEAD") {
    init.body = call.body;
    init.duplex = "half";
  }

  return fetch(buildBackendUrl(call.path), init);
}

export function toBrowserResponse(upstream: Response): Response {
  const headers = new Headers();

  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);

    if (value) {
      headers.set(name, value);
    }
  }

  if (upstream.status === 204 || upstream.status === 304) {
    return new Response(null, { status: upstream.status, headers });
  }

  return new Response(upstream.body, { status: upstream.status, headers });
}

export function buildSessionCookies(
  accessToken: string,
  expiresInSeconds: number,
  secure: boolean,
): { session: string; expiry: string } {
  const accessMaxAge = safeSessionMaxAge(expiresInSeconds);
  const expiresAt = Date.now() + accessMaxAge * 1000;
  const suffix = secure ? "; Secure" : "";

  return {
    session: `${SESSION_COOKIE}=${accessToken}; Path=/; Max-Age=${SESSION_MARKER_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax${suffix}`,
    expiry: `${SESSION_EXP_COOKIE}=${expiresAt}; Path=/; Max-Age=${SESSION_MARKER_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax${suffix}`,
  };
}

export function buildClearSessionCookies(secure: boolean): string[] {
  const suffix = secure ? "; Secure" : "";
  return [
    `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax${suffix}`,
    `${SESSION_EXP_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax${suffix}`,
    `${SESSION_REFRESH_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax${suffix}`,
    `${SESSION_CSRF_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax${suffix}`,
  ];
}

export function mirrorSessionSecrets(setCookies: readonly string[], secure: boolean): string[] {
  const suffix = secure ? "; Secure" : "";
  const refresh = extractCookieValue(setCookies, REFRESH_COOKIE);
  const csrf = extractCookieValue(setCookies, CSRF_COOKIE);
  const mirrored: string[] = [];

  if (refresh) {
    mirrored.push(
      `${SESSION_REFRESH_COOKIE}=${refresh}; Path=/; Max-Age=${SESSION_MARKER_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax${suffix}`,
    );
  }

  if (csrf) {
    mirrored.push(
      `${SESSION_CSRF_COOKIE}=${csrf}; Path=/; Max-Age=${SESSION_MARKER_MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax${suffix}`,
    );
  }

  return mirrored;
}

export function attachCookies(response: Response, cookies: readonly string[]): Response {
  for (const cookie of cookies) {
    response.headers.append("Set-Cookie", cookie);
  }

  return response;
}

export function expiredResponse(): Response {
  return Response.json(
    {
      type: "about:blank",
      title: "Session expired",
      status: 401,
      detail: "The session is no longer valid.",
      instance: "/api/v1",
      code: SESSION_EXPIRED_CODE,
      request_id: "",
    },
    {
      status: 401,
      headers: { "content-type": "application/problem+json" },
    },
  );
}

function refresh(request: NextRequest, signal?: AbortSignal) {
  return requestRefresh({
    cookies: request.cookies,
    backendUrl: buildBackendUrl("/api/v1/auth/refresh"),
    signal,
  });
}

function sessionCookies(
  outcome: RefreshOutcome,
  session: { session: string; expiry: string },
  secure: boolean,
): string[] {
  const mirrored =
    outcome.kind === "refreshed" ? mirrorSessionSecrets(outcome.setCookies, secure) : [];
  const backendCookies = outcome.kind === "refreshed" ? outcome.setCookies : [];

  return [...backendCookies, ...mirrored, session.session, session.expiry];
}

function rotatedCookies(outcome: RefreshOutcome): string[] {
  return outcome.kind === "failed" ? outcome.setCookies : [];
}

export type SessionRequestOptions = {
  request: NextRequest;
  path: string;
  method: string;
  body?: BodyInit | null;
  signal?: AbortSignal;
};

function expired(request: NextRequest, outcome: RefreshOutcome): SessionResult {
  return {
    response: attachCookies(expiredResponse(), [
      ...rotatedCookies(outcome),
      ...buildClearSessionCookies(
        isSecureRequest(request.url, request.headers.get("x-forwarded-proto")),
      ),
    ]),
    refreshed: false,
    expired: true,
  };
}

export async function sessionRequest(options: SessionRequestOptions): Promise<SessionResult> {
  const secure = isSecureRequest(
    options.request.url,
    options.request.headers.get("x-forwarded-proto"),
  );
  const token = readSessionToken(options.request.cookies);
  const needsRefresh = token === undefined || isSessionExpiring(options.request.cookies);

  if (needsRefresh) {
    const outcome = await refresh(options.request, options.signal);

    if (outcome.kind !== "refreshed") {
      return expired(options.request, outcome);
    }

    const upstream = await callBackend({
      ...options,
      accessToken: outcome.session.accessToken,
    });
    const session = buildSessionCookies(
      outcome.session.accessToken,
      outcome.session.expiresInSeconds,
      secure,
    );

    return {
      response: attachCookies(
        toBrowserResponse(upstream),
        sessionCookies(outcome, session, secure),
      ),
      refreshed: true,
      expired: false,
    };
  }

  const upstream = await callBackend({ ...options, accessToken: token });

  if (upstream.status !== 401) {
    return {
      response: toBrowserResponse(upstream),
      refreshed: false,
      expired: false,
    };
  }

  const outcome = await refresh(options.request, options.signal);

  if (outcome.kind !== "refreshed") {
    return expired(options.request, outcome);
  }

  const retry = await callBackend({
    ...options,
    accessToken: outcome.session.accessToken,
  });
  const session = buildSessionCookies(
    outcome.session.accessToken,
    outcome.session.expiresInSeconds,
    secure,
  );

  return {
    response: attachCookies(toBrowserResponse(retry), sessionCookies(outcome, session, secure)),
    refreshed: true,
    expired: false,
  };
}

export async function refreshOnly(request: NextRequest): Promise<SessionResult> {
  const secure = isSecureRequest(request.url, request.headers.get("x-forwarded-proto"));
  const outcome = await refresh(request);

  if (outcome.kind !== "refreshed") {
    return expired(request, outcome);
  }

  const session = buildSessionCookies(
    outcome.session.accessToken,
    outcome.session.expiresInSeconds,
    secure,
  );

  return {
    response: attachCookies(
      Response.json(outcome.session.user ?? null, {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
      sessionCookies(outcome, session, secure),
    ),
    refreshed: true,
    expired: false,
  };
}
