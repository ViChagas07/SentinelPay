import type { TranslationKey } from "@/lib/i18n";

export type AuthErrorKind =
  | "invalid_credentials"
  | "email_not_verified"
  | "too_many_attempts"
  | "rate_limited"
  | "password_policy_violation"
  | "invalid_auth_token"
  | "auth_not_configured"
  | "csrf_invalid"
  | "network_error"
  | "invalid_request"
  | "unknown";

const ERROR_KEYS: Record<AuthErrorKind, TranslationKey> = {
  invalid_credentials: "auth.errors.invalid_credentials",
  email_not_verified: "auth.errors.email_not_verified",
  too_many_attempts: "auth.errors.too_many_attempts",
  rate_limited: "auth.errors.rate_limited",
  password_policy_violation: "auth.errors.password_policy",
  invalid_auth_token: "auth.errors.invalid_token",
  auth_not_configured: "auth.errors.not_configured",
  csrf_invalid: "auth.errors.security_check",
  network_error: "auth.errors.network",
  invalid_request: "auth.errors.invalid_request",
  unknown: "auth.errors.unknown",
};

const KNOWN: readonly AuthErrorKind[] = [
  "invalid_credentials",
  "email_not_verified",
  "too_many_attempts",
  "rate_limited",
  "password_policy_violation",
  "invalid_auth_token",
  "auth_not_configured",
  "csrf_invalid",
  "network_error",
  "invalid_request",
  "unknown",
];

export function toAuthErrorKind(code: string | null | undefined): AuthErrorKind {
  if (!code) {
    return "unknown";
  }

  return (KNOWN as readonly string[]).includes(code) ? (code as AuthErrorKind) : "unknown";
}

export function authErrorKey(code: string | null | undefined): TranslationKey {
  return ERROR_KEYS[toAuthErrorKind(code)];
}

export type AuthProblem = {
  status: number;
  code: string;
  retryAfterSeconds: number | null;
  violations: string[];
};

export function parseAuthProblem(payload: unknown, status: number): AuthProblem {
  const source = typeof payload === "object" && payload !== null ? payload : {};
  const record = source as Record<string, unknown>;
  const code = typeof record.code === "string" ? record.code : "unknown";
  const retryAfter = record.retry_after;
  const retryAfterSeconds =
    typeof retryAfter === "number" && Number.isFinite(retryAfter)
      ? retryAfter
      : typeof record.retry_after_seconds === "number"
        ? record.retry_after_seconds
        : null;
  const violations = Array.isArray(record.violations)
    ? record.violations.filter((item): item is string => typeof item === "string")
    : [];

  return { status, code, retryAfterSeconds, violations };
}

export function readRetryAfter(response: Response): number | null {
  const header = response.headers.get("retry-after");

  if (!header) {
    return null;
  }

  const parsed = Number(header);
  return Number.isFinite(parsed) && parsed > 0 ? Math.ceil(parsed) : null;
}
