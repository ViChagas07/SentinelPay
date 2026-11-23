export const LOGIN_MODES = ["signin", "signup"] as const;

export type LoginMode = (typeof LOGIN_MODES)[number];

export const DEFAULT_LOGIN_MODE: LoginMode = "signin";
export const LOGIN_MODE_PARAM = "modo";
export const LOGIN_MODE_SIGNUP_VALUE = "cadastro";

export function parseLoginMode(value: string | null | undefined): LoginMode {
  return value === LOGIN_MODE_SIGNUP_VALUE ? "signup" : DEFAULT_LOGIN_MODE;
}

export function buildLoginModeUrl(
  current: { pathname: string; search: string; hash: string },
  mode: LoginMode,
): string {
  const params = new URLSearchParams(current.search);

  if (mode === "signup") {
    params.set(LOGIN_MODE_PARAM, LOGIN_MODE_SIGNUP_VALUE);
  } else {
    params.delete(LOGIN_MODE_PARAM);
  }

  const query = params.toString();
  return `${current.pathname}${query ? `?${query}` : ""}${current.hash}`;
}
