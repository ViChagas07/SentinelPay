"use client";

import { useI18n } from "@/lib/i18n/provider";

const STEPS = [
  { titleKey: "verification.steps.1.title", bodyKey: "verification.steps.1.body" },
  { titleKey: "verification.steps.2.title", bodyKey: "verification.steps.2.body" },
  { titleKey: "verification.steps.3.title", bodyKey: "verification.steps.3.body" },
] as const;

export function VerificationSteps() {
  const { t } = useI18n();

  return (
    <section aria-labelledby="verification-steps-title" className="min-w-0">
      <h2
        id="verification-steps-title"
        className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground"
      >
        {t("verification.steps.label")}
      </h2>
      <ol className="mt-4 space-y-4">
        {STEPS.map((step, index) => (
          <li key={step.titleKey} className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border font-mono text-[0.65rem]">
              {index + 1}
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-medium">{t(step.titleKey)}</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {t(step.bodyKey)}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-5 border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
        {t("verification.disclaimer")}
      </p>
    </section>
  );
}
