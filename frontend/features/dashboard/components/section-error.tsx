"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type SectionErrorProps = {
  onRetry: () => void;
  message?: string;
  className?: string;
};

export function SectionError({ onRetry, message, className }: SectionErrorProps) {
  const { t } = useI18n();

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-[6px] border border-border bg-card p-5",
        className,
      )}
    >
      <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
        {t("dashboard.error.title")}
      </p>
      <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
        {message ?? t("dashboard.error.description")}
      </p>
      <Button type="button" variant="outline" size="sm" onClick={onRetry}>
        <RefreshCw aria-hidden="true" />
        {t("dashboard.error.retry")}
      </Button>
    </div>
  );
}
