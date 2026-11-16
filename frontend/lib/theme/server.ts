import { cookies } from "next/headers";

import { THEME_COOKIE, resolveThemeMode, type ThemeMode } from "./constants";

export async function getServerTheme(): Promise<ThemeMode> {
  const cookieStore = await cookies();
  return resolveThemeMode(cookieStore.get(THEME_COOKIE)?.value);
}
