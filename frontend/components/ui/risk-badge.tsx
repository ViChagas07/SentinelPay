"use client";

import type { RiskBand } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { getRiskPresentation } from "@/lib/risk/presentation";
import { cn } from "@/lib/utils";

export type RiskBadgeProps = {
  band: RiskBand;
  showIcon?: boolean;
  className?: string;
};

export function RiskBadge({ band, showIcon = true, className }: RiskBadgeProps) {
  const { t } = useI18n();
  const presentation = getRiskPresentation(band);
  const Icon = presentation.icon;

  return (
    <span
      data-band={band}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[6px] border px-2 py-0.5 text-xs font-medium text-foreground",
        className,
      )}
      style={{
        borderColor: `color-mix(in srgb, ${presentation.color} 45%, var(--border))`,
        backgroundColor: `color-mix(in srgb, ${presentation.color} 8%, var(--surface))`,
      }}
    >
      {showIcon ? (
        <Icon
          className="size-3.5 shrink-0"
          style={{ color: presentation.color }}
          aria-hidden="true"
        />
      ) : null}
      <span>{t(presentation.labelKey)}</span>
    </span>
  );
}

export type ClassDotProps = {
  band: RiskBand;
  label?: string;
  className?: string;
};

export function ClassDot({ band, label, className }: ClassDotProps) {
  const presentation = getRiskPresentation(band);

  return (
    <span
      className={cn("inline-block size-2 shrink-0 rounded-full", className)}
      style={{ backgroundColor: presentation.color }}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}
