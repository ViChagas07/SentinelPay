import { LOGIN_PATH, PRIVATE_PATHS, PUBLIC_PATHS } from "./constants";

export type RouteKind = "public" | "private" | "other";

function normalizePath(pathname: string): string {
  if (pathname.length === 0) {
    return "/";
  }

  const withoutTrailingSlash =
    pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;

  return withoutTrailingSlash.startsWith("/") ? withoutTrailingSlash : `/${withoutTrailingSlash}`;
}

function matchesPrefix(pathname: string, base: string): boolean {
  if (base === "/") {
    return pathname === "/";
  }

  return pathname === base || pathname.startsWith(`${base}/`);
}

export function getRouteKind(pathname: string): RouteKind {
  const normalized = normalizePath(pathname);

  if (normalized === LOGIN_PATH) {
    return "public";
  }

  if (PUBLIC_PATHS.some((publicPath) => matchesPrefix(normalized, publicPath))) {
    return "public";
  }

  if (PRIVATE_PATHS.some((privatePath) => matchesPrefix(normalized, privatePath))) {
    return "private";
  }

  return "other";
}

export function isSafeNextPath(candidate: string | null | undefined): candidate is string {
  if (!candidate) {
    return false;
  }

  if (!candidate.startsWith("/") || candidate.startsWith("//")) {
    return false;
  }

  if (candidate.includes("\\") || candidate.includes("\n") || candidate.includes("\r")) {
    return false;
  }

  const withoutQuery = candidate.split("?")[0] ?? "";

  if (withoutQuery === LOGIN_PATH || withoutQuery.startsWith(`${LOGIN_PATH}/`)) {
    return false;
  }

  return getRouteKind(withoutQuery) === "private";
}

export function resolveNextPath(candidate: string | null | undefined, fallback: string): string {
  return isSafeNextPath(candidate) ? candidate : fallback;
}

export function buildLoginRedirect(pathname: string, search: string): string {
  const target = `${normalizePath(pathname)}${search}`;
  return `${LOGIN_PATH}?next=${encodeURIComponent(target)}`;
}

export type AuthDecision = { action: "next" } | { action: "redirect"; location: string };

export function decideAuthAction(options: {
  pathname: string;
  search: string;
  hasSession: boolean;
}): AuthDecision {
  const normalized = normalizePath(options.pathname);
  const kind = getRouteKind(normalized);

  if (kind === "private" && !options.hasSession) {
    return { action: "redirect", location: buildLoginRedirect(normalized, options.search) };
  }

  if (normalized === LOGIN_PATH && options.hasSession) {
    const nextParam = new URLSearchParams(options.search).get("next");

    if (nextParam && isSafeNextPath(nextParam)) {
      return { action: "redirect", location: nextParam };
    }

    return { action: "redirect", location: "/painel" };
  }

  return { action: "next" };
}
