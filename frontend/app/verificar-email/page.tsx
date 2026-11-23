import type { Metadata } from "next";

import { VerifyEmailView } from "@/features/auth/components/verify-email-view";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();

  return {
    title: `${serverTranslate(locale, "auth.verify.title")} | ${serverTranslate(locale, "app.name")}`,
    robots: { index: false, follow: false },
    referrer: "no-referrer",
  };
}

type SearchValue = string | string[] | undefined;

function readParam(value: SearchValue): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }

  return value ?? null;
}

export default async function VerifyEmailPage({
  searchParams,
}: Readonly<{ searchParams: Promise<Record<string, SearchValue>> }>) {
  const params = await searchParams;

  return <VerifyEmailView token={readParam(params.token)} />;
}
