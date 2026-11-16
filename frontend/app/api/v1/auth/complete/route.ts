import { NextResponse, type NextRequest } from "next/server";

import { buildBackendUrl } from "@/lib/api/config";
import { requestRefresh, toLoginErrorCode } from "@/lib/session/backend";
import {
  APP_HOME_PATH,
  LOGIN_PATH,
  OIDC_NEXT_COOKIE,
  SESSION_EXPIRED_REASON,
} from "@/lib/session/constants";
import { isSecureRequest, readOidcNext } from "@/lib/session/cookies";
import { isSafeNextPath } from "@/lib/session/routes";
import {
  buildClearSessionCookies,
  buildSessionCookies,
  mirrorSessionSecrets,
} from "@/lib/session/server";

export const dynamic = "force-dynamic";

function loginRedirect(request: NextRequest, params: Array<[string, string]>): URL {
  const url = new URL(LOGIN_PATH, request.url);

  for (const [key, value] of params) {
    url.searchParams.set(key, value);
  }

  return url;
}

function clearNextCookie(response: NextResponse, secure: boolean): void {
  response.cookies.set({
    name: OIDC_NEXT_COOKIE,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 0,
  });
}

export async function GET(request: NextRequest) {
  const secure = isSecureRequest(request.url, request.headers.get("x-forwarded-proto"));
  const pendingNext = readOidcNext(request.cookies);
  const destination = isSafeNextPath(pendingNext) ? pendingNext : APP_HOME_PATH;
  const outcome = await requestRefresh({
    cookies: request.cookies,
    backendUrl: buildBackendUrl("/api/v1/auth/refresh"),
  });

  if (outcome.kind !== "refreshed") {
    const errorCode = outcome.kind === "failed" ? toLoginErrorCode(outcome.code) : null;
    const params: Array<[string, string]> = [];

    if (errorCode) {
      params.push(["reason", "auth_failed"], ["code", errorCode]);
    } else if (pendingNext) {
      params.push(["next", pendingNext], ["reason", SESSION_EXPIRED_REASON]);
    } else {
      params.push(["reason", SESSION_EXPIRED_REASON]);
    }

    const response = NextResponse.redirect(loginRedirect(request, params));
    clearNextCookie(response, secure);

    for (const cookie of outcome.kind === "failed" ? outcome.setCookies : []) {
      response.headers.append("Set-Cookie", cookie);
    }

    for (const cookie of buildClearSessionCookies(secure)) {
      response.headers.append("Set-Cookie", cookie);
    }

    return response;
  }

  const session = buildSessionCookies(
    outcome.session.accessToken,
    outcome.session.expiresInSeconds,
    secure,
  );
  const mirrored = mirrorSessionSecrets(outcome.setCookies, secure);
  const response = NextResponse.redirect(new URL(destination, request.url));

  for (const cookie of outcome.setCookies) {
    response.headers.append("Set-Cookie", cookie);
  }

  for (const cookie of mirrored) {
    response.headers.append("Set-Cookie", cookie);
  }

  response.headers.append("Set-Cookie", session.session);
  response.headers.append("Set-Cookie", session.expiry);
  clearNextCookie(response, secure);

  return response;
}
