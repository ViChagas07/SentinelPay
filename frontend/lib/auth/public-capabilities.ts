import { buildBackendUrl } from "@/lib/api/config";

export const PUBLIC_CAPABILITIES_PATH = "auth/capabilities";
export const PUBLIC_PASSWORD_POLICY_PATH = "auth/password-policy";

const TIMEOUT_MS = 8_000;

const CAPABILITIES_FALLBACK: Record<string, unknown> = {
  password_enabled: true,
  signup_enabled: false,
  password_reset_enabled: false,
  google_enabled: true,
};

const PASSWORD_POLICY_FALLBACK: Record<string, unknown> = {
  min_length: 10,
  max_length: 128,
  requirements: ["min_length", "max_length", "not_common", "not_personal"],
  hibp_enabled: false,
};

function capabilitiesFallback(): Record<string, unknown> {
  const flag = process.env.AUTH_PASSWORD_ENABLED?.trim().toLowerCase();
  const disabled = flag === "false" || flag === "0";
  const optIn = flag === "true";

  return {
    ...CAPABILITIES_FALLBACK,
    password_enabled: !disabled,
    signup_enabled: optIn,
    password_reset_enabled: optIn,
  };
}

function fallbackFor(path: string): Record<string, unknown> | null {
  if (path === PUBLIC_CAPABILITIES_PATH) {
    return capabilitiesFallback();
  }

  if (path === PUBLIC_PASSWORD_POLICY_PATH) {
    return PASSWORD_POLICY_FALLBACK;
  }

  return null;
}

export function publicJsonResponse(payload: unknown, status: number): Response {
  return Response.json(payload, {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
    },
  });
}

export async function fetchPublicJson(path: string): Promise<Record<string, unknown> | null> {
  const fallback = fallbackFor(path);

  if (!fallback) {
    return null;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const upstream = await fetch(buildBackendUrl(`/api/v1/${path}`), {
      method: "GET",
      headers: { accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!upstream.ok) {
      return fallback;
    }

    const payload: unknown = await upstream.json().catch(() => null);

    return payload !== null && typeof payload === "object"
      ? (payload as Record<string, unknown>)
      : fallback;
  } catch {
    return fallback;
  } finally {
    clearTimeout(timeout);
  }
}
