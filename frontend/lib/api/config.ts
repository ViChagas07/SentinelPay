const DEFAULT_API_URL = "http://localhost:8000";

export const API_V1_PREFIX = "/api/v1";

export function getInternalApiBaseUrl(): string {
  const configured =
    process.env.API_INTERNAL_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    DEFAULT_API_URL;

  return configured.replace(/\/+$/, "");
}

export function getPublicApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();

  if (!configured) {
    return "";
  }

  return configured.replace(/\/+$/, "");
}

export function buildBackendUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getInternalApiBaseUrl()}${normalizedPath}`;
}

export function buildPublicBackendUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getPublicApiBaseUrl()}${normalizedPath}`;
}
