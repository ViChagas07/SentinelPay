"use client";

import { Check, X } from "lucide-react";

import type { PasswordPolicy } from "@/lib/auth/capabilities";
import { passwordIssues, passwordStrength } from "@/lib/auth/password";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const STRENGTH_LABELS = {
  weak: "auth.password.strengthWeak",
  fair: "auth.password.strengthFair",
  good: "auth.password.strengthGood",
  strong: "auth.password.strengthStrong",
} as const;

const STRENGTH_BARS = {
  weak: "bg-foreground/40",
  fair: "bg-petrol-primary/60",
  good: "bg-petrol-primary",
  strong: "bg-petrol-primary",
} as const;

const STRENGTH_LEVELS = { weak: 1, fair: 2, good: 3, strong: 4 } as const;

export type PasswordStrengthMeterProps = {
  value: string;
  policy: PasswordPolicy;
  identifiers: readonly string[];
};

export function PasswordStrengthMeter({ value, policy, identifiers }: PasswordStrengthMeterProps) {
  const { t } = useI18n();
  const strength = passwordStrength(value, policy);
  const level = STRENGTH_LEVELS[strength];
  const issues = passwordIssues(value, policy, identifiers);
  const checks = [
    {
      key: "min_length",
      ok: !issues.includes("too_short"),
      label: t("auth.password.requirementLength", { count: policy.minLength }),
    },
    {
      key: "not_common",
      ok: !issues.includes("too_common"),
      label: t("auth.password.requirementCommon"),
    },
    {
      key: "not_personal",
      ok: !issues.includes("contains_identifier"),
      label: t("auth.password.requirementPersonal"),
    },
  ];

  if (!value) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div
          className="flex flex-1 gap-1"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={4}
          aria-valuenow={level}
          aria-valuetext={t(STRENGTH_LABELS[strength])}
        >
          {[1, 2, 3, 4].map((step) => (
            <span
              key={step}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors",
                step <= level ? STRENGTH_BARS[strength] : "bg-border",
              )}
              aria-hidden="true"
            />
          ))}
        </div>
        <span className="text-xs text-muted-foreground" aria-live="polite">
          {t(STRENGTH_LABELS[strength])}
        </span>
      </div>
      <ul className="space-y-1">
        {checks.map((check) => (
          <li
            key={check.key}
            className={cn(
              "flex items-center gap-1.5 text-xs leading-relaxed",
              check.ok ? "text-muted-foreground" : "text-foreground/70",
            )}
          >
            {check.ok ? (
              <Check className="size-3 shrink-0" aria-hidden="true" />
            ) : (
              <X className="size-3 shrink-0" aria-hidden="true" />
            )}
            {check.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
