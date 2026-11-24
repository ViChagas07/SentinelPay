const DEFAULT_API_URL = "http://localhost:8000";

export const API_V1_PREFIX = "/api/v1";

export class ApiConfigurationError extends Error {
  constructor() {
    super("The internal API base URL is not configured.");
    this.name = "ApiConfigurationError";
  }
}

function stripQuotes(value: string): string {
  const trimmed = value.trim();

  if (
    trimmed.length >= 2 &&
    ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'")))
  ) {
    return trimmed.slice(1, -1).trim();
  }

  return trimmed;
}

function isLocalHost(value: string): boolean {
  const host = value.split("/")[0]?.split(":")[0]?.toLowerCase();
  return host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0" || host === "[::1]";
}

export function normalizeBaseUrl(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const stripped = stripQuotes(value);

  if (!stripped) {
    return null;
  }

  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(stripped)
    ? stripped
    : `${isLocalHost(stripped) ? "http" : "https"}://${stripped}`;

  try {
    const parsed = new URL(withScheme);

    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }

    if (parsed.search || parsed.hash || parsed.username || parsed.password) {
      return null;
    }

    if (
      !parsed.hostname ||
      (!parsed.hostname.startsWith("[") && !/^[a-z0-9._-]+$/i.test(parsed.hostname))
    ) {
      return null;
    }

    const path = parsed.pathname.replace(/\/+$/, "").replace(/\/api\/v1$/i, "");
    return `${parsed.origin}${path}`;
  } catch {
    return null;
  }
}

function configuredBaseUrl(): string | null {
  const configured =
    process.env.API_INTERNAL_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim();

  if (configured) {
    return normalizeBaseUrl(configured);
  }

  return process.env.NODE_ENV === "production" ? null : DEFAULT_API_URL;
}

export function getInternalApiBaseUrl(): string {
  return configuredBaseUrl() ?? "";
}

export function getPublicApiBaseUrl(): string {
  return normalizeBaseUrl(process.env.NEXT_PUBLIC_API_URL) ?? "";
}

export function buildBackendUrl(path: string): string {
  const base = getInternalApiBaseUrl();

  if (!base) {
    throw new ApiConfigurationError();
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

export function buildPublicBackendUrl(path: string): string {
  const base = getPublicApiBaseUrl();

  if (!base) {
    return "";
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}
