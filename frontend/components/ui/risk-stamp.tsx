"use client";

import type { RiskBand } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { getRiskPresentation } from "@/lib/risk/presentation";
import { cn } from "@/lib/utils";

export type RiskStampProps = {
  band: RiskBand;
  className?: string;
};

export function RiskStamp({ band, className }: RiskStampProps) {
  const { t } = useI18n();
  const presentation = getRiskPresentation(band);
  const label = t(presentation.labelKey);

  return (
    <span
      data-band={band}
      className={cn(
        "inline-flex -rotate-2 items-center gap-2 rounded-[6px] border px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-foreground",
        className,
      )}
      style={{
        borderColor: presentation.color,
        backgroundColor: `color-mix(in srgb, ${presentation.color} 8%, var(--surface))`,
      }}
    >
      <span
        className="size-1.5 rounded-full"
        style={{ backgroundColor: presentation.color }}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
