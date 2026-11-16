"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { useI18n } from "@/lib/i18n/provider";
import type { ShellBreadcrumb } from "@/lib/shell/routes";

export function Breadcrumbs({ items }: Readonly<{ items: readonly ShellBreadcrumb[] }>) {
  const { t } = useI18n();

  if (items.length === 0) {
    return null;
  }

  return (
    <nav aria-label={t("shell.breadcrumbs.label")} className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
        {items.map((item, index) => {
          const last = index === items.length - 1;

          return (
            <li key={`${item.labelKey}-${index}`} className="flex min-w-0 items-center gap-1">
              {index > 0 ? <ChevronRight className="size-3 shrink-0" aria-hidden="true" /> : null}
              {item.href && !last ? (
                <Link href={item.href} className="truncate hover:text-foreground">
                  {t(item.labelKey)}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className="truncate text-foreground">
                  {t(item.labelKey)}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
