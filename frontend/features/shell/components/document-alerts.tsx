"use client";

import { useEffect } from "react";

import { useI18n } from "@/lib/i18n/provider";
import { alertIconHref, buildAlertTitle } from "@/lib/shell/alerts";

export type DocumentAlertsProps = {
  count: number;
  truncated: boolean;
  baseTitle: string;
};

export function DocumentAlerts({ count, truncated, baseTitle }: DocumentAlertsProps) {
  const { t } = useI18n();

  useEffect(() => {
    const desiredTitle = buildAlertTitle({
      count,
      truncated,
      baseTitle,
      appName: t("app.name"),
    });

    function applyTitle() {
      if (document.title !== desiredTitle) {
        document.title = desiredTitle;
      }
    }

    applyTitle();

    const observer = new MutationObserver(applyTitle);
    observer.observe(document.head, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    const href = alertIconHref(count);
    const existing = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="icon"]'));
    let created: HTMLLinkElement | null = null;

    if (existing.length === 0) {
      created = document.createElement("link");
      created.rel = "icon";
      created.type = "image/svg+xml";
      document.head.appendChild(created);
    }

    const icons = created ? [created] : existing;

    for (const icon of icons) {
      icon.setAttribute("href", href);
    }

    return () => {
      observer.disconnect();

      for (const icon of icons) {
        icon.setAttribute("href", "/icon.svg");
      }

      created?.remove();
    };
  }, [baseTitle, count, t, truncated]);

  return null;
}
