import type { Metadata } from "next";

import { LegalPage } from "@/features/legal/components/legal-page";
import { legalContent } from "@/lib/legal/content";
import { resolveLegalIdentity } from "@/lib/legal/identity";
import { getServerLocale } from "@/lib/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();
  const document = legalContent[locale].privacy;

  return { title: document.title, description: document.subtitle };
}

export default async function Page() {
  const locale = await getServerLocale();
  const identity = resolveLegalIdentity(process.env);

  return <LegalPage kind="privacy" content={legalContent[locale].privacy} identity={identity} />;
}
