import type { NextRequest } from "next/server";

import { buildBackendUrl } from "@/lib/api/config";
import { readErrorCode, readSetCookies } from "@/lib/session/backend";
import { isSecureRequest } from "@/lib/session/cookies";
import { buildSessionCookies, mirrorSessionSecrets } from "@/lib/session/server";

export type PasswordProxyResult = {
  response: Response;
  status: number;
};

const FORWARD_HEADERS = ["accept-language", "user-agent"];

export function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");

  if (!origin) {
    const referer = request.headers.get("referer");

    if (!referer) {
      return false;
    }

    try {
      return new URL(referer).origin === request.nextUrl.origin;
    } catch {
      return false;
    }
  }

  try {
    return new URL(origin).origin === request.nextUrl.origin;
  } catch {
    return false;
  }
}

function originRejected(): Response {
  return Response.json(
    {
      type: "about:blank",
      title: "Forbidden",
      status: 403,
      detail: "The request origin is not allowed.",
      instance: "/api/v1",
      code: "csrf_invalid",
      request_id: "",
    },
    { status: 403, headers: { "content-type": "application/problem+json" } },
  );
}

function forwardHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  headers.set("content-type", "application/json");
  headers.set("accept", "application/json");

  for (const name of FORWARD_HEADERS) {
    const value = request.headers.get(name);

    if (value) {
      headers.set(name, value);
    }
  }

  return headers;
}

function clientIp(request: NextRequest): string | null {
  const forwarded = request.headers.get("x-forwarded-for");
  const first = forwarded?.split(",")[0]?.trim();
  return first || request.headers.get("x-real-ip") || null;
}

export async function passwordAuthProxy(options: {
  request: NextRequest;
  path: string;
  body: unknown;
  withSession?: boolean;
}): Promise<PasswordProxyResult> {
  if (!sameOrigin(options.request)) {
    return { response: originRejected(), status: 403 };
  }

  const headers = forwardHeaders(options.request);
  const ip = clientIp(options.request);

  if (ip) {
    headers.set("x-forwarded-for", ip);
  }

  let accessToken: string | null = null;

  if (options.withSession) {
    accessToken = options.request.cookies.get("sp_session")?.value ?? null;
  }

  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }

  let upstream: Response;

  try {
    upstream = await fetch(buildBackendUrl(options.path), {
      method: "POST",
      headers,
      body: JSON.stringify(options.body),
      cache: "no-store",
      signal: options.request.signal,
    });
  } catch {
    return {
      response: Response.json(
        {
          type: "about:blank",
          title: "Bad gateway",
          status: 502,
          detail: "The authentication service is unavailable.",
          instance: "/api/v1",
          code: "network_error",
          request_id: "",
        },
        { status: 502, headers: { "content-type": "application/problem+json" } },
      ),
      status: 502,
    };
  }

  const setCookies = readSetCookies(upstream.headers);
  const secure = isSecureRequest(
    options.request.url,
    options.request.headers.get("x-forwarded-proto"),
  );

  if (!upstream.ok) {
    const code = await readErrorCode(upstream);
    const retryAfter = upstream.headers.get("retry-after");
    const headersOut = new Headers({
      "content-type": "application/problem+json",
    });

    if (retryAfter) {
      headersOut.set("retry-after", retryAfter);
    }

    return {
      response: Response.json(
        {
          type: "about:blank",
          title: upstream.status === 429 ? "Too many requests" : "Authentication failed",
          status: upstream.status,
          detail: code,
          instance: "/api/v1",
          code,
          request_id: upstream.headers.get("x-request-id") ?? "",
        },
        { status: upstream.status, headers: headersOut },
      ),
      status: upstream.status,
    };
  }

  if (upstream.status === 204) {
    return { response: new Response(null, { status: 204 }), status: 204 };
  }

  const payload = (await upstream.json().catch(() => null)) as {
    access_token?: unknown;
    expires_in?: unknown;
    user?: unknown;
  } | null;

  if (
    payload &&
    typeof payload.access_token === "string" &&
    typeof payload.expires_in === "number" &&
    payload.expires_in > 0
  ) {
    const session = buildSessionCookies(payload.access_token, payload.expires_in, secure);
    const mirrored = mirrorSessionSecrets(setCookies, secure);
    const response = Response.json(
      { user: payload.user ?? null },
      { status: 200, headers: { "content-type": "application/json" } },
    );

    for (const cookie of [...setCookies, ...mirrored, session.session, session.expiry]) {
      response.headers.append("Set-Cookie", cookie);
    }

    return { response, status: 200 };
  }

  const accepted = Response.json(
    { status: "accepted" },
    { status: 202, headers: { "content-type": "application/json" } },
  );

  for (const cookie of setCookies) {
    accepted.headers.append("Set-Cookie", cookie);
  }

  return { response: accepted, status: 202 };
}
