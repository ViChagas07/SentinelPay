import { cookies } from "next/headers";

import { LOCALE_COOKIE, resolveLocale, type Locale } from "./constants";
import type { TranslationKey } from "./dictionaries";
import { translate, type TranslationParams } from "./translate";

export async function getServerLocale(): Promise<Locale> {
  const cookieStore = await cookies();
  return resolveLocale(cookieStore.get(LOCALE_COOKIE)?.value);
}

export function serverTranslate(
  locale: Locale,
  key: TranslationKey,
  params?: TranslationParams,
): string {
  return translate(locale, key, params);
}
