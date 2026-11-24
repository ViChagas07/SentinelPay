import { NextResponse, type NextRequest } from "next/server";

import { hasSessionCookie, readOidcNext } from "@/lib/session/cookies";
import { decideAuthAction } from "@/lib/session/routes";

const AUTH_COMPLETE_PATH = "/api/v1/auth/complete";

function isDesignRoute(pathname: string): boolean {
  return pathname === "/dev/design" || pathname.startsWith("/dev/design/");
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (isDesignRoute(pathname)) {
    if (process.env.NODE_ENV !== "development") {
      return new NextResponse(null, { status: 404 });
    }

    return NextResponse.next();
  }

  if (pathname === AUTH_COMPLETE_PATH) {
    return NextResponse.next();
  }

  if (readOidcNext(request.cookies)) {
    const completeUrl = request.nextUrl.clone();
    const ticket = request.nextUrl.searchParams.get("ticket");
    completeUrl.pathname = AUTH_COMPLETE_PATH;
    completeUrl.search = ticket ? `?ticket=${encodeURIComponent(ticket)}` : "";
    return NextResponse.redirect(completeUrl);
  }

  const decision = decideAuthAction({
    pathname,
    search,
    hasSession: hasSessionCookie(request.cookies),
  });

  if (decision.action === "redirect") {
    return NextResponse.redirect(new URL(decision.location, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api/|_next/static|_next/image|favicon.ico|icon.svg|favicon-alert.svg|.*\\.[a-z0-9]+$).*)",
  ],
};
