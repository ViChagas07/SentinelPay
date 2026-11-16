const DEFAULT_SITE_URL = "http://localhost:3000";

function normalizeHttpUrl(value: string | undefined): string | null {
  const candidate = value?.trim();

  if (!candidate) {
    return null;
  }

  try {
    const url = new URL(candidate);

    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }

    return url.toString();
  } catch {
    return null;
  }
}

export function getSiteUrl(): string {
  const configured = normalizeHttpUrl(process.env.NEXT_PUBLIC_SITE_URL);

  if (!configured) {
    return DEFAULT_SITE_URL;
  }

  return new URL(configured).origin;
}

export function getSupportExternalUrl(configured: string | undefined): string | null {
  return normalizeHttpUrl(configured);
}

export function resolveSupportHref(configured: string | undefined): string {
  return getSupportExternalUrl(configured) ?? "/suporte";
}
