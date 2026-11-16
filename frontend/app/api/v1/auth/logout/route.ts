import { NextResponse, type NextRequest } from "next/server";

import { buildBackendUrl } from "@/lib/api/config";
import { readSetCookies, buildCsrfHeaders } from "@/lib/session/backend";
import { isSecureRequest } from "@/lib/session/cookies";
import { buildClearSessionCookies } from "@/lib/session/server";
import { SESSION_CSRF_COOKIE, SESSION_REFRESH_COOKIE } from "@/lib/session/constants";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const secure = isSecureRequest(request.url, request.headers.get("x-forwarded-proto"));
  const headers = buildCsrfHeaders(request.cookies);
  const cookieHeader = request.cookies
    .getAll()
    .filter(
      (cookie) =>
        cookie.name === "refresh_token" ||
        cookie.name === "csrf_token" ||
        cookie.name === SESSION_REFRESH_COOKIE ||
        cookie.name === SESSION_CSRF_COOKIE,
    )
    .map((cookie) => {
      const name =
        cookie.name === SESSION_REFRESH_COOKIE
          ? "refresh_token"
          : cookie.name === SESSION_CSRF_COOKIE
            ? "csrf_token"
            : cookie.name;
      return `${name}=${cookie.value}`;
    })
    .join("; ");

  let upstream: Response | null = null;

  try {
    upstream = await fetch(buildBackendUrl("/api/v1/auth/logout"), {
      method: "POST",
      headers: {
        ...Object.fromEntries(headers.entries()),
        Cookie: cookieHeader,
      },
      cache: "no-store",
    });
  } catch {
    upstream = null;
  }

  const response = new NextResponse(null, { status: 204 });

  if (upstream) {
    for (const cookie of readSetCookies(upstream.headers)) {
      response.headers.append("Set-Cookie", cookie);
    }
  }

  for (const cookie of buildClearSessionCookies(secure)) {
    response.headers.append("Set-Cookie", cookie);
  }

  return response;
}
