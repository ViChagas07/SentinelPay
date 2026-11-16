// Revisão jurídica pendente: o texto desta página é um rascunho funcional e
// precisa ser validado por responsável legal antes do uso público em produção.
import type { Metadata } from "next";

import { LegalPage } from "@/features/legal/components/legal-page";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();
  return { title: serverTranslate(locale, "terms.title") };
}

export default function Page() {
  return <LegalPage kind="terms" />;
}
