"use client";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import type { LegalDocument } from "@/lib/legal/content/types";
import type { LegalIdentity } from "@/lib/legal/identity";
import type { LegalDocumentKind } from "@/lib/legal/version";

import { LegalDocumentView } from "./legal-document";

export type LegalPageProps = {
  kind: LegalDocumentKind;
  content: LegalDocument;
  identity: LegalIdentity;
};

export function LegalPage({ kind, content, identity }: LegalPageProps) {
  return (
    <div className="legal-page-shell flex min-h-dvh flex-col">
      <div className="contents print:hidden">
        <SiteHeader />
      </div>
      <main id="conteudo" className="flex-1">
        <div className="mx-auto w-full max-w-6xl px-5 pb-24 pt-10 sm:px-8 lg:pt-16">
          <LegalDocumentView kind={kind} content={content} identity={identity} />
        </div>
      </main>
      <div className="contents print:hidden">
        <SiteFooter />
      </div>
    </div>
  );
}
