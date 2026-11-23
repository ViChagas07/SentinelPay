import type { Metadata } from "next";

import { ForgotPasswordView } from "@/features/auth/components/forgot-password-view";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();

  return {
    title: `${serverTranslate(locale, "auth.forgot.title")} | ${serverTranslate(locale, "app.name")}`,
    robots: { index: false, follow: false },
  };
}

export default function ForgotPasswordPage() {
  return <ForgotPasswordView />;
}
