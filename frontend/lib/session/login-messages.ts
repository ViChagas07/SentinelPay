import type { TranslationKey } from "@/lib/i18n";
import { LOGIN_PATH, isLoginErrorCode, type LoginErrorCode } from "./constants";

export const BUILD_LOGIN_ERROR_KEYS: Record<
  LoginErrorCode | "forbidden" | "session_expired",
  TranslationKey
> = {
  invalid_state: "auth.login.errors.invalid_state",
  google_auth_failed: "auth.login.errors.google_auth_failed",
  email_not_verified: "auth.login.errors.email_not_verified",
  too_many_attempts: "auth.login.errors.too_many_attempts",
  rate_limited: "auth.login.errors.rate_limited",
  rate_limit_unavailable: "auth.login.errors.rate_limit_unavailable",
  security_service_unavailable: "auth.login.errors.security_service_unavailable",
  auth_not_configured: "auth.login.errors.auth_not_configured",
  csrf_invalid: "auth.login.errors.csrf_invalid",
  network_error: "auth.login.errors.network_error",
  forbidden: "auth.login.errors.forbidden",
  session_expired: "auth.login.errors.session_expired",
};

export function buildLoginPath(options: { next?: string; reason?: string; code?: string }): string {
  const params = new URLSearchParams();

  if (options.next) {
    params.set("next", options.next);
  }

  if (options.reason) {
    params.set("reason", options.reason);
  }

  if (options.code) {
    params.set("code", options.code);
  }

  const query = params.toString();
  return query.length > 0 ? `${LOGIN_PATH}?${query}` : LOGIN_PATH;
}

export function loginErrorKey(code: string | null | undefined): TranslationKey | null {
  if (code === "forbidden") {
    return BUILD_LOGIN_ERROR_KEYS.forbidden;
  }

  if (code === "session_expired") {
    return BUILD_LOGIN_ERROR_KEYS.session_expired;
  }

  if (isLoginErrorCode(code)) {
    return BUILD_LOGIN_ERROR_KEYS[code];
  }

  return null;
}
