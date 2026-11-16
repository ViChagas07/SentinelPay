export const SESSION_COOKIE = "sp_session";
export const SESSION_EXP_COOKIE = "sp_session_exp";
export const SESSION_REFRESH_COOKIE = "sp_refresh";
export const SESSION_CSRF_COOKIE = "sp_csrf";
export const OIDC_NEXT_COOKIE = "sp_oidc";

export const REFRESH_COOKIE = "refresh_token";
export const CSRF_COOKIE = "csrf_token";
export const CSRF_HEADER = "X-CSRF-Token";

export const LOGIN_PATH = "/login";
export const APP_HOME_PATH = "/painel";

export const OIDC_NEXT_MAX_AGE_SECONDS = 600;
export const SESSION_COOKIE_MAX_AGE_FALLBACK = 900;
export const SESSION_MARKER_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

export const PUBLIC_PATHS = ["/", LOGIN_PATH, "/termos", "/privacidade"] as const;

export const PRIVATE_PATHS = [
  "/painel",
  "/verificacao",
  "/boletos",
  "/folha",
  "/pagamentos",
  "/inteligencia",
  "/notificacoes",
  "/account",
] as const;

export const SESSION_EXPIRED_CODE = "session_expired";
export const SESSION_EXPIRED_REASON = "expired";
export const AUTH_FAILED_REASON = "auth_failed";

export const LOGIN_ERROR_CODES = [
  "invalid_state",
  "google_auth_failed",
  "email_not_verified",
  "too_many_attempts",
  "rate_limited",
  "rate_limit_unavailable",
  "security_service_unavailable",
  "auth_not_configured",
  "csrf_invalid",
  "network_error",
] as const;

export type LoginErrorCode = (typeof LOGIN_ERROR_CODES)[number];

export function isLoginErrorCode(value: string | null | undefined): value is LoginErrorCode {
  return LOGIN_ERROR_CODES.some((code) => code === value);
}
