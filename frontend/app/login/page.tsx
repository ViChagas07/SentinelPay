import type { Metadata } from "next";

import { LoginView } from "@/features/auth/components/login-view";
import { loadLoginCapabilities } from "@/lib/auth/login-capabilities";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();

  return {
    title: `${serverTranslate(locale, "auth.login.eyebrow")} | ${serverTranslate(locale, "app.name")}`,
    description: serverTranslate(locale, "auth.login.description"),
    robots: { index: false, follow: false },
  };
}

type SearchValue = string | string[] | undefined;

function readParam(value: SearchValue): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }

  return value;
}

export default async function LoginPage({
  searchParams,
}: Readonly<{ searchParams: Promise<Record<string, SearchValue>> }>) {
  const params = await searchParams;
  const capabilities = await loadLoginCapabilities();

  return (
    <LoginView
      passwordEnabled={capabilities.passwordEnabled}
      signupEnabled={capabilities.signupEnabled}
      passwordResetEnabled={capabilities.passwordResetEnabled}
      policy={capabilities.policy}
      search={{
        next: readParam(params.next),
        reason: readParam(params.reason),
        code: readParam(params.code),
        error: readParam(params.error),
        modo: readParam(params.modo),
      }}
    />
  );
}
