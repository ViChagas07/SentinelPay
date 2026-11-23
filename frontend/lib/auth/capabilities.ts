import { buildBackendUrl } from "@/lib/api/config";

export type AuthCapabilities = {
  passwordEnabled: boolean;
  googleEnabled: boolean;
};

const DISABLED: AuthCapabilities = { passwordEnabled: false, googleEnabled: true };

function envPasswordEnabled(): boolean {
  return process.env.AUTH_PASSWORD_ENABLED === "true";
}

export async function fetchAuthCapabilities(
  fetchImpl: typeof fetch = fetch,
): Promise<AuthCapabilities> {
  try {
    const response = await fetchImpl(buildBackendUrl("/api/v1/auth/capabilities"), {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });

    if (!response.ok) {
      return { ...DISABLED, passwordEnabled: envPasswordEnabled() };
    }

    const payload = (await response.json()) as {
      password_enabled?: unknown;
      google_enabled?: unknown;
    };

    return {
      passwordEnabled: payload.password_enabled === true,
      googleEnabled: payload.google_enabled !== false,
    };
  } catch {
    return { ...DISABLED, passwordEnabled: envPasswordEnabled() };
  }
}

export type PasswordPolicy = {
  minLength: number;
  maxLength: number;
  requirements: string[];
  hibpEnabled: boolean;
};

export const FALLBACK_POLICY: PasswordPolicy = {
  minLength: 10,
  maxLength: 128,
  requirements: ["min_length", "max_length", "not_common", "not_personal"],
  hibpEnabled: false,
};

export async function fetchPasswordPolicy(
  fetchImpl: typeof fetch = fetch,
): Promise<PasswordPolicy> {
  try {
    const response = await fetchImpl(buildBackendUrl("/api/v1/auth/password-policy"), {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });

    if (!response.ok) {
      return FALLBACK_POLICY;
    }

    const payload = (await response.json()) as {
      min_length?: unknown;
      max_length?: unknown;
      requirements?: unknown;
      hibp_enabled?: unknown;
    };

    const minLength =
      typeof payload.min_length === "number" && payload.min_length > 0
        ? payload.min_length
        : FALLBACK_POLICY.minLength;
    const maxLength =
      typeof payload.max_length === "number" && payload.max_length > minLength
        ? payload.max_length
        : FALLBACK_POLICY.maxLength;
    const requirements = Array.isArray(payload.requirements)
      ? payload.requirements.filter((item): item is string => typeof item === "string")
      : FALLBACK_POLICY.requirements;

    return {
      minLength,
      maxLength,
      requirements,
      hibpEnabled: payload.hibp_enabled === true,
    };
  } catch {
    return FALLBACK_POLICY;
  }
}
