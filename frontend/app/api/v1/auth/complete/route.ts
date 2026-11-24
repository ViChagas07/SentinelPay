import { NextResponse, type NextRequest } from "next/server";

import { ApiConfigurationError, buildBackendUrl } from "@/lib/api/config";
import {
  requestRefresh,
  requestTicketExchange,
  toLoginErrorCode,
  type RefreshOutcome,
  type TicketOutcome,
} from "@/lib/session/backend";
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

type SessionOutcome = RefreshOutcome | TicketOutcome;

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

function failureRedirect(
  request: NextRequest,
  outcome: SessionOutcome,
  pendingNext: string | undefined,
  secure: boolean,
): NextResponse {
  const errorCode =
    outcome.kind === "failed" ? (toLoginErrorCode(outcome.code) ?? "google_auth_failed") : null;
  const params: Array<[string, string]> = [];

  if (errorCode) {
    params.push(["reason", "auth_failed"], ["code", errorCode], ["error", errorCode]);
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

function successRedirect(
  request: NextRequest,
  outcome: Extract<SessionOutcome, { kind: "refreshed" }>,
  destination: string,
  secure: boolean,
): NextResponse {
  const session = buildSessionCookies(
    outcome.session.accessToken,
    outcome.session.expiresInSeconds,
    secure,
  );
  const mirrored = mirrorSessionSecrets(outcome.setCookies, secure);
  const response = NextResponse.redirect(new URL(destination, request.url));
  clearNextCookie(response, secure);

  for (const cookie of outcome.setCookies) {
    response.headers.append("Set-Cookie", cookie);
  }

  for (const cookie of mirrored) {
    response.headers.append("Set-Cookie", cookie);
  }

  response.headers.append("Set-Cookie", session.session);
  response.headers.append("Set-Cookie", session.expiry);

  return response;
}

function configurationFailure(): TicketOutcome {
  return { kind: "failed", code: "auth_not_configured", status: 503, setCookies: [] };
}

export async function GET(request: NextRequest) {
  const secure = isSecureRequest(request.url, request.headers.get("x-forwarded-proto"));
  const pendingNext = readOidcNext(request.cookies);
  const destination = isSafeNextPath(pendingNext) ? pendingNext : APP_HOME_PATH;
  const ticket = request.nextUrl.searchParams.get("ticket")?.trim();

  if (ticket) {
    let outcome: TicketOutcome;
    const clientIp =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      request.headers.get("x-real-ip");

    try {
      outcome = await requestTicketExchange({
        ticket,
        backendUrl: buildBackendUrl("/api/v1/auth/session-ticket"),
        clientIp,
        signal: request.signal,
      });
    } catch (error) {
      if (error instanceof ApiConfigurationError) {
        outcome = configurationFailure();
      } else {
        throw error;
      }
    }

    if (outcome.kind !== "refreshed") {
      return failureRedirect(request, outcome, pendingNext, secure);
    }

    return successRedirect(request, outcome, destination, secure);
  }

  let outcome: RefreshOutcome;

  try {
    outcome = await requestRefresh({
      cookies: request.cookies,
      backendUrl: buildBackendUrl("/api/v1/auth/refresh"),
      signal: request.signal,
    });
  } catch (error) {
    if (error instanceof ApiConfigurationError) {
      outcome = configurationFailure();
    } else {
      throw error;
    }
  }

  if (outcome.kind !== "refreshed") {
    return failureRedirect(request, outcome, pendingNext, secure);
  }

  return successRedirect(request, outcome, destination, secure);
}
