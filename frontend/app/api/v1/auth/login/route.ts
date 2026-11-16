import { NextResponse, type NextRequest } from "next/server";

import { buildBackendUrl } from "@/lib/api/config";
import { OIDC_NEXT_COOKIE, OIDC_NEXT_MAX_AGE_SECONDS } from "@/lib/session/constants";
import { isSecureRequest } from "@/lib/session/cookies";
import { resolveNextPath } from "@/lib/session/routes";
import { APP_HOME_PATH } from "@/lib/session/constants";

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
