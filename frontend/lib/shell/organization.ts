export type ShellOrganization = {
  id: string;
  name: string;
  plan: string;
};

export function getSupportUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_SUPPORT_URL?.trim();

  if (!raw) {
    return null;
  }

  try {
    const url = new URL(raw);

    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }

    return url.toString();
  } catch {
    return null;
  }
}
