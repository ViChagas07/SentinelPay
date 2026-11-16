let apiLocale: string | undefined;

export function setApiLocale(locale: string | undefined): void {
  apiLocale = locale;
}

export function getApiLocale(): string | undefined {
  return apiLocale;
}
