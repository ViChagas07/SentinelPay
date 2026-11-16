"use client";

import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";

import { Sparkline } from "@/components/ui/sparkline";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type StatChangeDirection = "up" | "down" | "flat";

export type StatChange = {
  value: string;
  direction: StatChangeDirection;
  label?: string;
};

export type StatBlockProps = {
  label: string;
  value: string;
  change?: StatChange;
  sparkline?: readonly number[];
  className?: string;
};

const CHANGE_ICONS: Record<StatChangeDirection, LucideIcon> = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  flat: Minus,
};

const CHANGE_LABEL_KEYS: Record<StatChangeDirection, TranslationKey> = {
  up: "design.statBlock.changeUp",
  down: "design.statBlock.changeDown",
  flat: "design.statBlock.changeFlat",
};

export function StatBlock({ label, value, change, sparkline, className }: StatBlockProps) {
  const { t } = useI18n();
  const ChangeIcon = change ? CHANGE_ICONS[change.direction] : null;

  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-4 rounded-[6px] border border-border bg-card p-5",
        className,
      )}
    >
      <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <p className="font-serif text-5xl leading-none tracking-tight">{value}</p>
      <div className="flex items-end justify-between gap-4">
        {change && ChangeIcon ? (
          <span
            className="inline-flex min-w-0 items-center gap-1.5 font-mono text-xs text-muted-foreground"
            aria-label={`${change.value} ${t(CHANGE_LABEL_KEYS[change.direction])}${
              change.label ? `, ${change.label}` : ""
            }`}
          >
            <ChangeIcon className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="text-foreground">{change.value}</span>
            {change.label ? <span className="truncate">{change.label}</span> : null}
          </span>
        ) : null}
        {sparkline ? (
          <Sparkline data={sparkline} width={96} height={28} className="ml-auto text-primary" />
        ) : null}
      </div>
    </div>
  );
}
