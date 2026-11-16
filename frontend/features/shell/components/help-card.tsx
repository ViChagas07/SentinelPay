"use client";

import { LifeBuoy } from "lucide-react";

import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type HelpCardProps = {
  supportUrl: string;
  collapsed: boolean;
};

export function HelpCard({ supportUrl, collapsed }: HelpCardProps) {
  const { t } = useI18n();

  return (
    <a
      href={supportUrl}
      target="_blank"
      rel="noreferrer"
      aria-label={collapsed ? t("shell.sidebar.help.cta") : undefined}
      className={cn(
        "flex items-center gap-2 rounded-[6px] border border-on-petrol/20 bg-petrol-active/40 px-2.5 py-2 text-on-petrol transition-colors hover:bg-petrol-active",
        collapsed && "justify-center",
      )}
    >
      <LifeBuoy className="size-4 shrink-0" aria-hidden="true" />
      {collapsed ? null : (
        <span className="min-w-0">
          <span className="block text-xs font-medium">{t("shell.sidebar.help.title")}</span>
          <span className="block truncate text-[0.65rem] text-on-petrol/75">
            {t("shell.sidebar.help.description")}
          </span>
        </span>
      )}
    </a>
  );
}
