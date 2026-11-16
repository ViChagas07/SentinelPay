"use client";

import {
  AlertTriangle,
  Check,
  FileText,
  Layers,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { RiskRuler } from "@/components/ui/risk-ruler";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { SectionHeading } from "./section-heading";
import styles from "../landing.module.css";

const STEP_KEYS = [
  { title: "landing.how.step1Title", body: "landing.how.step1Body" },
  { title: "landing.how.step2Title", body: "landing.how.step2Body" },
  { title: "landing.how.step3Title", body: "landing.how.step3Body" },
] as const;

function DiagramFrame({ children, label }: Readonly<{ children: ReactNode; label: string }>) {
  return (
    <div className="flex min-h-[420px] flex-col rounded-[6px] border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
        <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </span>
        <span className="size-1.5 rounded-full bg-petrol-500" aria-hidden="true" />
      </div>
      <div className="flex flex-1 flex-col justify-center pt-6">{children}</div>
    </div>
  );
}

function UploadVisual({ label }: Readonly<{ label: string }>) {
  const { t } = useI18n();

  return (
    <DiagramFrame label={label}>
      <div className="grid items-center gap-4 sm:grid-cols-[1fr_auto_1.1fr]">
        <div className="rounded-[4px] border border-border bg-surface-elevated p-3">
          <div className="flex items-center gap-2 border-b border-border pb-2">
            <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
              {t("landing.how.pdfLabel")}
            </span>
          </div>
          <div className="mt-3 space-y-2" aria-hidden="true">
            <span className="block h-1.5 w-4/5 rounded-full bg-border" />
            <span className="block h-1.5 w-3/5 rounded-full bg-border" />
            <span className="block h-1.5 w-2/3 rounded-full bg-border" />
            <span className="block h-8 w-full rounded-[3px] bg-border/70" />
          </div>
        </div>
        <div className="hidden justify-center sm:flex" aria-hidden="true">
          <span className="h-px w-8 bg-border" />
        </div>
        <div className="rounded-[4px] border border-primary/40 bg-surface-elevated p-4">
          <LockKeyhole className="size-6 text-primary" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium">{t("landing.how.uploadAuth")}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t("landing.how.uploadCheck2")}
          </p>
        </div>
      </div>
      <ul className="mt-6 space-y-2 border-t border-border pt-4 text-sm">
        {(
          [
            "landing.how.uploadCheck1",
            "landing.how.uploadCheck2",
            "landing.how.uploadCheck3",
          ] as const
        ).map((key) => (
          <li key={key} className="flex items-center gap-2">
            <Check className="size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>{t(key)}</span>
          </li>
        ))}
      </ul>
    </DiagramFrame>
  );
}

function AnalysisVisual({ label }: Readonly<{ label: string }>) {
  const { t } = useI18n();

  return (
    <DiagramFrame label={label}>
      <div className="relative">
        <div
          className="absolute -left-2 top-3 h-full w-full rounded-[4px] border border-border bg-surface-elevated"
          aria-hidden="true"
        />
        <div
          className="absolute -left-1 top-1.5 h-full w-full rounded-[4px] border border-border bg-surface"
          aria-hidden="true"
        />
        <div className="relative rounded-[4px] border border-border bg-surface-elevated p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-2 font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
              <ScanLine className="size-4" aria-hidden="true" />
              {t("landing.hero.reading")}
            </span>
            <span className="size-1.5 rounded-full bg-petrol-500" aria-hidden="true" />
          </div>
          <div className="mt-3 space-y-2" aria-hidden="true">
            <span className="block h-1.5 w-5/6 rounded-full bg-border" />
            <span className="block h-1.5 w-2/3 rounded-full bg-border" />
            <span className="block h-1.5 w-3/4 rounded-full bg-border" />
            <span className="block h-1.5 w-1/2 rounded-full bg-border" />
          </div>
        </div>
      </div>
      <div className="mt-8 grid gap-2 sm:grid-cols-2">
        {(
          [
            { icon: Check, key: "landing.how.analysisRules" },
            { icon: Layers, key: "landing.how.analysisModel" },
            { icon: ScanLine, key: "landing.how.analysisVisual" },
            { icon: ShieldCheck, key: "landing.how.analysisKnowledge" },
          ] as const
        ).map((item) => {
          const Icon = item.icon;

          return (
            <div
              key={item.key}
              className="flex items-center gap-2 rounded-[4px] border border-border bg-surface-elevated px-3 py-2 text-xs"
            >
              <Icon className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
              <span>{t(item.key)}</span>
            </div>
          );
        })}
      </div>
    </DiagramFrame>
  );
}

function DecisionVisual({ label }: Readonly<{ label: string }>) {
  const { t } = useI18n();

  return (
    <DiagramFrame label={label}>
      <div className="rounded-[4px] border border-border bg-surface-elevated p-4">
        <RiskRuler score={68} band="attention" variant="large" />
      </div>
      <div className="mt-4 space-y-2">
        <div className="flex items-center gap-2 rounded-[4px] border border-border bg-surface px-3 py-2 text-sm">
          <AlertTriangle className="size-4 shrink-0 text-risk-medium" aria-hidden="true" />
          <span>{t("landing.how.decisionEvidence")}</span>
        </div>
        <div className="flex items-center gap-2 rounded-[4px] border border-border bg-surface px-3 py-2 text-sm">
          <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span>{t("landing.how.decisionJustification")}</span>
        </div>
        <div className="flex items-center gap-2 rounded-[4px] border border-primary/40 bg-surface-elevated px-3 py-2 text-sm">
          <UserRound className="size-4 shrink-0 text-primary" aria-hidden="true" />
          <span>{t("landing.how.decisionReview")}</span>
        </div>
      </div>
    </DiagramFrame>
  );
}

function StepVisual({ step, label }: Readonly<{ step: number; label: string }>) {
  if (step === 0) {
    return <UploadVisual label={label} />;
  }

  if (step === 1) {
    return <AnalysisVisual label={label} />;
  }

  return <DecisionVisual label={label} />;
}

export function HowItWorks() {
  const { t } = useI18n();
  const [activeStep, setActiveStep] = useState(0);
  const stepRefs = useRef<Array<HTMLElement | null>>([]);

  useEffect(() => {
    let frame = 0;

    const updateActiveStep = () => {
      const anchor = window.innerHeight * 0.38;
      let nextStep = 0;

      stepRefs.current.forEach((element, index) => {
        if (element && element.getBoundingClientRect().top <= anchor) {
          nextStep = index;
        }
      });

      setActiveStep((current) => (current === nextStep ? current : nextStep));
    };

    const onScroll = () => {
      if (frame !== 0) {
        return;
      }

      frame = window.requestAnimationFrame(() => {
        frame = 0;
        updateActiveStep();
      });
    };

    updateActiveStep();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);

      if (frame !== 0) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, []);

  return (
    <section
      id="como-funciona"
      aria-labelledby="como-funciona-title"
      className="scroll-mt-24 border-b border-border"
    >
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
        <SectionHeading
          id="como-funciona-title"
          number="02"
          label={t("landing.how.eyebrow")}
          title={t("landing.how.titleLead")}
          accent={t("landing.how.titleAccent")}
          description={t("landing.how.description")}
        />

        <div className="mt-14 grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start lg:gap-16">
          <div>
            {STEP_KEYS.map((step, index) => (
              <article
                key={step.title}
                ref={(element) => {
                  stepRefs.current[index] = element;
                }}
                className={cn(
                  "border-t border-border py-10 first:border-t-0 first:pt-0 lg:min-h-[58vh] lg:py-16",
                  index === activeStep && "lg:border-petrol-500/40",
                )}
              >
                <div className="flex items-baseline gap-3">
                  <span
                    className={cn(
                      "font-mono text-xs tabular-nums",
                      index === activeStep ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    0{index + 1}
                  </span>
                  <h3 className="font-serif text-3xl leading-tight tracking-tight sm:text-4xl">
                    {t(step.title)}
                  </h3>
                </div>
                <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
                  {t(step.body)}
                </p>
                <div className="mt-8 lg:hidden">
                  <StepVisual step={index} label={t("landing.hero.demoLabel")} />
                </div>
              </article>
            ))}
          </div>

          <div className="hidden lg:block">
            <div className="sticky top-24">
              <div key={activeStep} className={styles.visualEnter}>
                <StepVisual step={activeStep} label={t("landing.hero.demoLabel")} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
