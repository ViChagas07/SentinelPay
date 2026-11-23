"use client";

import { LoaderCircle, Lock } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Wordmark } from "@/components/brand/logo";
import { LanguageSelector } from "@/components/language-selector";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { BackButton } from "@/features/auth/components/back-button";
import { useI18n } from "@/lib/i18n/provider";

export type AuthShellProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  const { t } = useI18n();
  const router = useRouter();

  return (
    <div className="grid min-h-dvh grid-cols-1 lg:h-dvh lg:grid-cols-[1.1fr_0.9fr] lg:overflow-hidden">
      <aside className="relative hidden flex-col justify-between border-r border-border bg-petrol-sidebar p-10 text-on-petrol lg:flex xl:p-14">
        <div className="flex flex-col items-start gap-5">
          <BackButton tone="onPetrol" />
          <Link href="/" aria-label={t("app.name")} className="w-fit rounded-[6px]">
            <Wordmark
              name={t("app.name")}
              className="text-on-petrol"
              variant="compactLight"
              size="large"
              priority
            />
          </Link>
        </div>
        <div className="max-w-lg">
          <p className="font-serif text-4xl leading-[1.05] tracking-tight xl:text-5xl">
            {t("auth.login.title")}
          </p>
          <p className="mt-5 max-w-md text-base leading-relaxed text-on-petrol/90">
            {t("auth.login.description")}
          </p>
        </div>
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.22em] text-on-petrol/90">
          {t("app.tagline")}
        </p>
      </aside>

      <main id="conteudo" className="flex min-h-dvh flex-col lg:h-dvh lg:min-h-0">
        <header className="flex items-start justify-between gap-4 px-5 pt-5 sm:px-8 lg:items-center lg:justify-end lg:py-5">
          <div className="flex flex-col items-start gap-2 lg:hidden">
            <BackButton />
            <Link href="/" aria-label={t("app.name")} className="rounded-[6px]">
              <Wordmark name={t("app.name")} />
            </Link>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <ThemeToggle />
            <LanguageSelector />
          </div>
        </header>

        <div className="flex min-h-0 flex-1 flex-col px-5 pb-10 sm:px-8 lg:overflow-y-auto">
          <div className="auth-form-enter mx-auto flex w-full max-w-[26.25rem] flex-1 flex-col py-8 lg:my-auto lg:flex-none">
            <h1 className="font-serif text-4xl leading-tight tracking-tight">{title}</h1>
            {subtitle ? (
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{subtitle}</p>
            ) : null}

            <div className="mt-8">{children}</div>

            {footer ? <div className="mt-6">{footer}</div> : null}

            <p className="mt-10 flex items-start gap-2 border-t border-border pt-6 text-xs leading-relaxed text-muted-foreground">
              <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {t("auth.login.trustSeal")}
            </p>

            <button
              type="button"
              onClick={() => router.push("/login")}
              className="mt-6 inline-flex min-h-11 w-fit items-center text-sm text-muted-foreground underline decoration-border underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {t("auth.verify.goToLogin")}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export function AuthNotice({
  tone,
  title,
  description,
}: {
  tone: "info" | "success" | "error";
  title: string;
  description: string;
}) {
  const role = tone === "error" ? "alert" : "status";

  return (
    <div className="rounded-[6px] border border-border bg-surface p-4" role={role}>
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}

export function SubmitButton({
  pending,
  label,
  pendingLabel,
}: {
  pending: boolean;
  label: string;
  pendingLabel: string;
}) {
  return (
    <Button
      type="submit"
      size="lg"
      aria-busy={pending}
      aria-disabled={pending}
      className="h-12 w-full gap-2 bg-petrol-base text-on-petrol hover:bg-petrol-base/90 disabled:opacity-60"
    >
      {pending ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : null}
      {pending ? pendingLabel : label}
    </Button>
  );
}
