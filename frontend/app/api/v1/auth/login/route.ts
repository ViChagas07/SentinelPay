import { NextResponse, type NextRequest } from "next/server";

import { buildBackendUrl } from "@/lib/api/config";
import { passwordAuthProxy } from "@/lib/session/password-auth";
import { OIDC_NEXT_COOKIE, OIDC_NEXT_MAX_AGE_SECONDS } from "@/lib/session/constants";
import { isSecureRequest } from "@/lib/session/cookies";
import { resolveNextPath } from "@/lib/session/routes";
import { APP_HOME_PATH } from "@/lib/session/constants";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  const next = resolveNextPath(request.nextUrl.searchParams.get("next"), APP_HOME_PATH);
  const secure = isSecureRequest(request.url, request.headers.get("x-forwarded-proto"));
  const target = new URL(buildBackendUrl("/api/v1/auth/google/login"));
  const response = NextResponse.redirect(target, { status: 302 });

  response.cookies.set({
    name: OIDC_NEXT_COOKIE,
    value: next,
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: OIDC_NEXT_MAX_AGE_SECONDS,
  });

  return response;
}

export async function POST(request: NextRequest) {
  const body: unknown = await request.json().catch(() => null);

  if (body === null || typeof body !== "object") {
    return Response.json(
      {
        type: "about:blank",
        title: "Unprocessable entity",
        status: 422,
        detail: "Invalid request body.",
        instance: "/api/v1",
        code: "invalid_request",
        request_id: "",
      },
      { status: 422, headers: { "content-type": "application/problem+json" } },
    );
  }

  const result = await passwordAuthProxy({
    request,
    path: "/api/v1/auth/login",
    body,
  });

  return result.response;
}

