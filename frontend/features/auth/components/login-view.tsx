"use client";

import { ArrowRight, LoaderCircle, LogIn } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo, Wordmark } from "@/components/brand/logo";
import { LanguageSelector } from "@/components/language-selector";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { PageTransition } from "@/components/ui/motion/page-transition";
import { useI18n } from "@/lib/i18n/provider";
import { loginErrorKey } from "@/lib/session/login-messages";
import { isSafeNextPath } from "@/lib/session/routes";

export type LoginSearchParams = {
  next?: string;
  reason?: string;
  code?: string;
};

export function LoginView({ search }: Readonly<{ search: LoginSearchParams }>) {
  const { t } = useI18n();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const next = isSafeNextPath(search.next) ? search.next : undefined;
  const errorKey =
    search.reason === "expired" ? loginErrorKey("session_expired") : loginErrorKey(search.code);
  const isDenied = search.reason === "forbidden";

  function startLogin() {
    setPending(true);
    const target = next
      ? `/api/v1/auth/login?next=${encodeURIComponent(next)}`
      : "/api/v1/auth/login";
    window.location.assign(target);
  }

  return (
    <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
      <aside className="relative hidden flex-col justify-between border-r border-border bg-petrol-sidebar p-10 text-on-petrol lg:flex xl:p-14">
        <Link href="/" aria-label={t("app.name")} className="w-fit rounded-[6px]">
          <Wordmark name={t("app.name")} className="text-on-petrol" variant="compactLight" />
        </Link>
        <div className="max-w-lg">
          <Eyebrow number="01" label={t("auth.login.eyebrow")} className="!text-on-petrol" />
          <h1 className="mt-6 font-serif text-5xl leading-[1.02] tracking-tight xl:text-6xl">
            {t("auth.login.title")}
          </h1>
          <p className="mt-6 max-w-md text-base leading-relaxed text-on-petrol">
            {t("auth.login.description")}
          </p>
          <ul className="mt-10 space-y-3 border-t border-on-petrol/20 pt-6">
            {[t("auth.login.point1"), t("auth.login.point2"), t("auth.login.point3")].map(
              (point) => (
                <li key={point} className="flex items-start gap-3 text-sm text-on-petrol/90">
                  <span
                    className="mt-2 block size-1 shrink-0 rounded-full bg-on-petrol/90"
                    aria-hidden="true"
                  />
                  <span>{point}</span>
                </li>
              ),
            )}
          </ul>
        </div>
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.22em] text-on-petrol/90">
          {t("app.tagline")}
        </p>
      </aside>

      <main id="conteudo" className="flex flex-col">
        <header className="flex items-center justify-between gap-4 px-5 py-5 sm:px-8 lg:justify-end">
          <Link href="/" className="lg:hidden" aria-label={t("app.name")}>
            <Wordmark name={t("app.name")} />
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <LanguageSelector />
          </div>
        </header>

        <div className="flex flex-1 items-center px-5 pb-16 sm:px-8">
          <PageTransition className="mx-auto w-full max-w-sm">
            <Logo className="mb-6 h-16 w-auto" title={t("app.name")} sizes="64px" />
            <Eyebrow number="02" label={t("auth.login.eyebrow")} className="lg:hidden" />
            <h2 className="mt-4 font-serif text-4xl leading-tight tracking-tight lg:mt-0">
              {t("auth.login.title")}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {t("auth.login.description")}
            </p>

            {isDenied ? (
              <div className="mt-6 rounded-[6px] border border-border bg-surface p-4" role="alert">
                <p className="text-sm font-medium">{t("auth.login.deniedTitle")}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {t("auth.login.deniedDescription")}
                </p>
              </div>
            ) : errorKey ? (
              <div className="mt-6 rounded-[6px] border border-border bg-surface p-4" role="alert">
                <p className="text-sm font-medium">{t("auth.login.errorTitle")}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t(errorKey)}</p>
              </div>
            ) : null}

            <div className="mt-8 space-y-3">
              <Button
                type="button"
                size="lg"
                className="w-full"
                onClick={startLogin}
                disabled={pending}
                aria-busy={pending}
              >
                {pending ? (
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                ) : (
                  <LogIn aria-hidden="true" />
                )}
                {pending ? t("auth.login.redirecting") : t("auth.login.continueWithGoogle")}
              </Button>
              {pending ? (
                <p className="text-center text-xs text-muted-foreground" aria-live="polite">
                  {t("auth.login.redirecting")}
                </p>
              ) : null}
            </div>

            <p className="mt-8 text-xs leading-relaxed text-muted-foreground">
              {t("auth.login.termsPrefix")}{" "}
              <Link href="/termos" className="text-foreground underline underline-offset-4">
                {t("auth.login.terms")}
              </Link>{" "}
              {t("auth.login.and")}{" "}
              <Link href="/privacidade" className="text-foreground underline underline-offset-4">
                {t("auth.login.privacy")}
              </Link>
              .
            </p>

            <button
              type="button"
              className="mt-6 inline-flex items-center gap-1 text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
              onClick={() => router.replace("/")}
            >
              {t("common.backHome")}
              <ArrowRight className="size-3" aria-hidden="true" />
            </button>
          </PageTransition>
        </div>
      </main>
    </div>
  );
}
