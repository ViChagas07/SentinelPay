"use client";

import { LoaderCircle, Lock } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useId, useRef, useState, type KeyboardEvent } from "react";

import { GoogleIcon } from "@/components/brand/google-icon";
import { Wordmark } from "@/components/brand/logo";
import { LanguageSelector } from "@/components/language-selector";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { BackButton } from "@/features/auth/components/back-button";
import {
  LOGIN_MODES,
  buildLoginModeUrl,
  parseLoginMode,
  type LoginMode,
} from "@/lib/auth/login-mode";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { useSecureContext } from "@/lib/security/use-secure-context";
import { loginErrorKey } from "@/lib/session/login-messages";
import { isSafeNextPath } from "@/lib/session/routes";
import { cn } from "@/lib/utils";

export type LoginSearchParams = {
  next?: string;
  reason?: string;
  code?: string;
  modo?: string;
};

const MODE_COPY: Record<
  LoginMode,
  {
    tab: TranslationKey;
    title: TranslationKey;
    subtitle: TranslationKey;
    google: TranslationKey;
    googleHint: TranslationKey | null;
    footerPrompt: TranslationKey;
    footerAction: TranslationKey;
  }
> = {
  signin: {
    tab: "auth.login.tabSignin",
    title: "auth.login.formTitle",
    subtitle: "auth.login.formSubtitle",
    google: "auth.login.continueWithGoogle",
    googleHint: null,
    footerPrompt: "auth.login.signupPrompt",
    footerAction: "auth.login.tabSignup",
  },
  signup: {
    tab: "auth.login.tabSignup",
    title: "auth.login.signupTitle",
    subtitle: "auth.login.signupSubtitle",
    google: "auth.login.signupWithGoogle",
    googleHint: "auth.login.signupGoogleHint",
    footerPrompt: "auth.login.signinPrompt",
    footerAction: "auth.login.tabSignin",
  },
};

export function LoginView({ search }: Readonly<{ search: LoginSearchParams }>) {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, setPending] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [acceptError, setAcceptError] = useState(false);
  const secureContext = useSecureContext();
  const acceptRef = useRef<HTMLInputElement | null>(null);
  const tabRefs = useRef<Partial<Record<LoginMode, HTMLButtonElement | null>>>({});
  const termsErrorId = useId();
  const mode = parseLoginMode(searchParams.get("modo") ?? search.modo);
  const copy = MODE_COPY[mode];
  const next = isSafeNextPath(search.next) ? search.next : undefined;
  const errorKey =
    search.reason === "expired" ? loginErrorKey("session_expired") : loginErrorKey(search.code);
  const isDenied = search.reason === "forbidden";
  const blocked = !accepted || pending;

  const changeMode = useCallback(
    (nextMode: LoginMode) => {
      if (nextMode === mode) {
        return;
      }

      router.push(
        buildLoginModeUrl(
          { pathname, search: searchParams.toString(), hash: window.location.hash },
          nextMode,
        ),
        { scroll: false },
      );
    },
    [mode, pathname, router, searchParams],
  );

  function handleTabKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const index = LOGIN_MODES.indexOf(mode);
    let nextIndex: number | null = null;

    if (event.key === "ArrowRight") {
      nextIndex = (index + 1) % LOGIN_MODES.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (index - 1 + LOGIN_MODES.length) % LOGIN_MODES.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = LOGIN_MODES.length - 1;
    }

    if (nextIndex === null) {
      return;
    }

    event.preventDefault();
    const nextMode = LOGIN_MODES[nextIndex];

    if (!nextMode) {
      return;
    }

    changeMode(nextMode);
    tabRefs.current[nextMode]?.focus();
  }

  function startLogin() {
    if (pending) {
      return;
    }

    if (!accepted) {
      setAcceptError(true);
      acceptRef.current?.focus();
      return;
    }

    setPending(true);
    const target = next
      ? `/api/v1/auth/login?next=${encodeURIComponent(next)}`
      : "/api/v1/auth/login";
    window.location.assign(target);
  }

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
          <div className="auth-form-enter mx-auto w-full max-w-[26.25rem] py-8 lg:my-auto">
            {isDenied ? (
              <div className="mb-8 rounded-[6px] border border-border bg-surface p-4" role="alert">
                <p className="text-sm font-medium">{t("auth.login.deniedTitle")}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {t("auth.login.deniedDescription")}
                </p>
              </div>
            ) : errorKey ? (
              <div className="mb-8 rounded-[6px] border border-border bg-surface p-4" role="alert">
                <p className="text-sm font-medium">{t("auth.login.errorTitle")}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t(errorKey)}</p>
              </div>
            ) : null}

            <div
              role="tablist"
              aria-label={t("auth.login.tabsLabel")}
              onKeyDown={handleTabKeyDown}
              className="grid grid-cols-2 gap-1 rounded-[6px] border border-border bg-surface p-1"
            >
              {LOGIN_MODES.map((tabMode) => {
                const selected = tabMode === mode;

                return (
                  <button
                    key={tabMode}
                    ref={(element) => {
                      tabRefs.current[tabMode] = element;
                    }}
                    type="button"
                    role="tab"
                    id={`login-tab-${tabMode}`}
                    aria-selected={selected}
                    aria-controls="login-panel"
                    tabIndex={selected ? 0 : -1}
                    onClick={() => changeMode(tabMode)}
                    className={cn(
                      "min-h-11 rounded-[4px] px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                      selected
                        ? "bg-petrol-base text-on-petrol shadow-sm"
                        : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground",
                    )}
                  >
                    {t(MODE_COPY[tabMode].tab)}
                  </button>
                );
              })}
            </div>

            <div
              role="tabpanel"
              id="login-panel"
              aria-labelledby={`login-tab-${mode}`}
              className="min-h-[28rem] pt-8"
            >
              <h1 className="font-serif text-4xl leading-tight tracking-tight lg:hidden">
                {t(copy.title)}
              </h1>
              <h2 className="hidden font-serif text-4xl leading-tight tracking-tight lg:block">
                {t(copy.title)}
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t(copy.subtitle)}
              </p>

              <form
                key={mode}
                className="auth-form-enter mt-8"
                noValidate
                onSubmit={(event) => {
                  event.preventDefault();
                  startLogin();
                }}
              >
                <div className="flex items-start gap-3">
                  <input
                    ref={acceptRef}
                    id="login-terms"
                    type="checkbox"
                    checked={accepted}
                    disabled={pending}
                    aria-invalid={acceptError || undefined}
                    aria-describedby={acceptError ? termsErrorId : undefined}
                    onChange={(event) => {
                      setAccepted(event.target.checked);

                      if (event.target.checked) {
                        setAcceptError(false);
                      }
                    }}
                    className={cn(
                      "mt-0.5 size-4 shrink-0 cursor-pointer accent-petrol-primary",
                      acceptError && "outline outline-2 outline-offset-2 outline-foreground/40",
                    )}
                  />
                  <label
                    htmlFor="login-terms"
                    className="min-h-11 cursor-pointer select-none text-sm leading-relaxed text-foreground"
                  >
                    {t("auth.login.acceptPrefix")}{" "}
                    <Link
                      href="/termos"
                      target="_blank"
                      rel="noreferrer"
                      className="underline decoration-border underline-offset-4 transition-colors hover:decoration-foreground"
                    >
                      {t("auth.login.terms")}
                    </Link>{" "}
                    {t("auth.login.and")}{" "}
                    <Link
                      href="/privacidade"
                      target="_blank"
                      rel="noreferrer"
                      className="underline decoration-border underline-offset-4 transition-colors hover:decoration-foreground"
                    >
                      {t("auth.login.privacy")}
                    </Link>
                    .
                  </label>
                </div>

                {acceptError ? (
                  <p
                    id={termsErrorId}
                    role="alert"
                    className="mt-2 text-sm font-medium leading-relaxed text-foreground"
                  >
                    {t("auth.login.acceptError")}
                  </p>
                ) : null}

                <Button
                  type="submit"
                  size="lg"
                  variant="outline"
                  aria-disabled={blocked}
                  aria-busy={pending}
                  className={cn(
                    "mt-6 h-12 w-full gap-3 border-border bg-surface text-foreground transition-[background-color,border-color,box-shadow] hover:bg-surface-elevated active:translate-y-px [&_svg]:size-5",
                    blocked && "cursor-not-allowed opacity-70 hover:bg-surface",
                  )}
                >
                  {pending ? (
                    <LoaderCircle className="animate-spin" aria-hidden="true" />
                  ) : (
                    <GoogleIcon className="size-5" />
                  )}
                  {pending ? t("auth.login.redirecting") : t(copy.google)}
                </Button>

                {copy.googleHint ? (
                  <p className="mt-3 text-center text-xs leading-relaxed text-muted-foreground">
                    {t(copy.googleHint)}
                  </p>
                ) : null}

                {pending ? (
                  <p className="mt-3 text-center text-xs text-muted-foreground" aria-live="polite">
                    {t("auth.login.redirecting")}
                  </p>
                ) : null}
              </form>

              <p className="mt-8 text-sm text-muted-foreground">
                {t(copy.footerPrompt)}{" "}
                <button
                  type="button"
                  onClick={() => {
                    const nextMode = mode === "signup" ? "signin" : "signup";
                    changeMode(nextMode);
                    tabRefs.current[nextMode]?.focus();
                  }}
                  className="min-h-11 font-medium text-foreground underline decoration-border underline-offset-4 transition-colors hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  {t(copy.footerAction)}
                </button>
              </p>

              {secureContext ? (
                <p className="mt-8 flex items-start gap-2 border-t border-border pt-6 text-xs leading-relaxed text-muted-foreground">
                  <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  {t("auth.login.trustSeal")}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
