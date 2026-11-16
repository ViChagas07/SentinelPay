export type PrivacyContact = {
  url: string | null;
  email: string | null;
  href: string;
  isFallback: boolean;
};

function normalizeHttpUrl(value: string | undefined): string | null {
  const candidate = value?.trim();

  if (!candidate) {
    return null;
  }

  try {
    const url = new URL(candidate);

    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }

    return url.toString();
  } catch {
    return null;
  }
}

export function normalizePrivacyEmail(value: string | undefined): string | null {
  const candidate = value?.trim();

  if (!candidate || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(candidate)) {
    return null;
  }

  return candidate;
}

export function resolvePrivacyContact(options: {
  url: string | undefined;
  email: string | undefined;
}): PrivacyContact {
  const url = normalizeHttpUrl(options.url);
  const email = url ? null : normalizePrivacyEmail(options.email);

  if (url) {
    return { url, email: normalizePrivacyEmail(options.email), href: url, isFallback: false };
  }

  if (email) {
    return { url: null, email, href: `mailto:${email}`, isFallback: false };
  }

  return { url: null, email: null, href: "/suporte", isFallback: true };
}

export function getPrivacyContactFromEnv(): PrivacyContact {
  return resolvePrivacyContact({
    url: process.env.NEXT_PUBLIC_PRIVACY_CONTACT_URL,
    email: process.env.NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL,
  });
}
