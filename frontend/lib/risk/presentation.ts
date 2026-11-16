import { AlertTriangle, OctagonAlert, ShieldCheck, type LucideIcon } from "lucide-react";

import type { RiskBand } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";

export type RiskPresentation = {
  band: RiskBand;
  labelKey: TranslationKey;
  color: string;
  tone: RiskBand;
  icon: LucideIcon;
};

const presentations: Record<RiskBand, Omit<RiskPresentation, "band">> = {
  low: {
    labelKey: "risk.low",
    color: "var(--risk-low)",
    tone: "low",
    icon: ShieldCheck,
  },
  attention: {
    labelKey: "risk.attention",
    color: "var(--risk-medium)",
    tone: "attention",
    icon: AlertTriangle,
  },
  high: {
    labelKey: "risk.high",
    color: "var(--risk-high)",
    tone: "high",
    icon: OctagonAlert,
  },
};

export function getRiskPresentation(band: RiskBand): RiskPresentation {
  return { band, ...presentations[band] };
}
