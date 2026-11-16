export const THEME_COOKIE = "theme";

export const THEME_MODES = ["system", "light", "dark"] as const;

export type ThemeMode = (typeof THEME_MODES)[number];

export const DEFAULT_THEME_MODE: ThemeMode = "system";

export function isThemeMode(value: string | undefined | null): value is ThemeMode {
  return value === "system" || value === "light" || value === "dark";
}

export function resolveThemeMode(value: string | undefined | null): ThemeMode {
  return isThemeMode(value) ? value : DEFAULT_THEME_MODE;
}
