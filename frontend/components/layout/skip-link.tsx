"use client";

import { useI18n } from "@/lib/i18n/provider";

export function SkipLink() {
  const { t } = useI18n();

  return (
    <a href="#conteudo" className="skip-link">
      {t("common.skipToContent")}
    </a>
  );
}
