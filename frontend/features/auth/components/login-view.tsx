"use client";

import { LoaderCircle, Lock } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useRef, useState, type KeyboardEvent } from "react";

import { GoogleIcon } from "@/components/brand/google-icon";
import { Wordmark } from "@/components/brand/logo";
import { LanguageSelector } from "@/components/language-selector";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { BackButton } from "@/features/auth/components/back-button";
import { FormField, PasswordField, TextField } from "@/features/auth/components/form-fields";
import { PasswordStrengthMeter } from "@/features/auth/components/password-strength-meter";
import type { PasswordPolicy } from "@/lib/auth/capabilities";
import { requestPasswordLogin, requestRegister } from "@/lib/auth/client";
import {
  buildLoginModeUrl,
  parseLoginMode,
  type LoginMode,
} from "@/lib/auth/login-mode";
import { resolveLoginVisibility } from "@/lib/auth/login-visibility";
import { identifierFragments, passwordIssues } from "@/lib/auth/password";
import { useDebouncedPasswordMatch } from "@/lib/auth/password-match";
import { emailSchema } from "@/lib/auth/schemas";
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
  error?: string;
  modo?: string;
};

export type LoginViewProps = {
  search: LoginSearchParams;
  passwordEnabled: boolean;
  signupEnabled: boolean;
  passwordResetEnabled: boolean;
  policy: PasswordPolicy | null;
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
    submit: TranslationKey;
    submitting: TranslationKey;
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
    submit: "auth.login.submitSignin",
    submitting: "auth.login.submittingSignin",
  },
  signup: {
    tab: "auth.login.tabSignup",
    title: "auth.login.signupTitle",
    subtitle: "auth.login.signupSubtitle",
    google: "auth.login.signupWithGoogle",
    googleHint: "auth.login.signupGoogleHint",
    footerPrompt: "auth.login.signinPrompt",
    footerAction: "auth.login.tabSignin",
    submit: "auth.login.submitSignup",
    submitting: "auth.login.submittingSignup",
  },
};

type FieldErrors = {
  email?: string;
  password?: string;
  name?: string;
  confirm?: string;
};

type GeneralError = {
  messageKey: TranslationKey;
  retryAfter: number | null;
  code: string;
};

export function LoginView({
  search,
  passwordEnabled,
  signupEnabled,
  passwordResetEnabled,
  policy,
}: Readonly<LoginViewProps>) {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, setPending] = useState(false);
  const [googlePending, setGooglePending] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [acceptError, setAcceptError] = useState(false);
  const [fields, setFields] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [touched, setTouched] = useState<Record<keyof FieldErrors, boolean>>({
    email: false,
    password: false,
    name: false,
    confirm: false,
  });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [generalError, setGeneralError] = useState<GeneralError | null>(null);
  const secureContext = useSecureContext();
  const acceptRef = useRef<HTMLInputElement | null>(null);
  const emailRef = useRef<HTMLInputElement | null>(null);
  const nameRef = useRef<HTMLInputElement | null>(null);
  const passwordRef = useRef<HTMLInputElement | null>(null);
  const confirmRef = useRef<HTMLInputElement | null>(null);
  const tabRefs = useRef<Partial<Record<LoginMode, HTMLButtonElement | null>>>({});
  const termsErrorId = useId();
  const requestedMode = parseLoginMode(searchParams.get("modo") ?? search.modo);
  const {
    formsEnabled,
    tabsVisible,
    availableModes,
    mode,
    passwordFieldsVisible,
  } = resolveLoginVisibility({
    passwordEnabled,
    signupEnabled,
    policyAvailable: policy !== null,
    requestedMode,
  });
  const copy = MODE_COPY[mode];
  const passwordMatch = useDebouncedPasswordMatch(fields.password, fields.confirm);
  const fieldsLocked = !accepted;
  const next = isSafeNextPath(search.next) ? search.next : undefined;
  const errorKey =
    search.reason === "expired"
      ? loginErrorKey("session_expired")
      : (loginErrorKey(search.code) ?? loginErrorKey(search.error));
  const isDenied = search.reason === "forbidden";
  const identifiers = identifierFragments(fields.email, fields.name);

  function changeMode(nextMode: LoginMode) {
    if (nextMode === mode) {
      return;
    }

    setGeneralError(null);
    setFieldErrors({});
    setTouched({ email: false, password: false, name: false, confirm: false });
    router.push(
      buildLoginModeUrl(
        { pathname, search: searchParams.toString(), hash: window.location.hash },
        nextMode,
      ),
      { scroll: false },
    );
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    const index = availableModes.indexOf(mode);
    let nextIndex: number | null = null;

    if (event.key === "ArrowRight") {
      nextIndex = (index + 1) % availableModes.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (index - 1 + availableModes.length) % availableModes.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = availableModes.length - 1;
    }

    if (nextIndex === null) {
      return;
    }

    event.preventDefault();
    const nextMode = availableModes[nextIndex];

    if (!nextMode) {
      return;
    }

    changeMode(nextMode);
    tabRefs.current[nextMode]?.focus();
  }

  function validateEmail(value: string): string | undefined {
    if (!value.trim()) {
      return t("auth.login.validation.emailRequired");
    }

    return emailSchema.safeParse(value).success ? undefined : t("auth.login.validation.email");
  }

  function validatePasswordField(value: string): string | undefined {
    if (!value) {
      return t("auth.login.validation.passwordRequired");
    }

    if (!formsEnabled || !policy) {
      return undefined;
    }

    const issues = passwordIssues(value, policy, identifiers);

    return issues.length === 0 ? undefined : t("auth.login.validation.passwordPolicy");
  }

  function validateConfirm(value: string): string | undefined {
    if (!value) {
      return t("auth.login.validation.confirmRequired");
    }

    return value === fields.password ? undefined : t("auth.login.validation.passwordMismatch");
  }

  function syncConfirmError(confirmValue: string, passwordValue: string): void {
    setFieldErrors((current) => ({
      ...current,
      confirm: !confirmValue
        ? current.confirm
        : confirmValue === passwordValue
          ? undefined
          : t("auth.login.validation.passwordMismatch"),
    }));
  }

  function startGoogleLogin() {
    if (googlePending) {
      return;
    }

    if (!accepted) {
      setAcceptError(true);
      acceptRef.current?.focus();
      return;
    }

    setGooglePending(true);
    const target = next
      ? `/api/v1/auth/login?next=${encodeURIComponent(next)}`
      : "/api/v1/auth/login";
    window.location.assign(target);
  }

  async function submitPasswordForm(): Promise<void> {
    if (pending || !passwordFieldsVisible) {
      return;
    }

    if (!accepted) {
      setAcceptError(true);
      acceptRef.current?.focus();
      return;
    }

    const errors: FieldErrors = {};
    const emailError = validateEmail(fields.email);
    const passwordError = validatePasswordField(fields.password);

    if (emailError) {
      errors.email = emailError;
    }

    if (passwordError) {
      errors.password = passwordError;
    }

    if (mode === "signup") {
      if (!fields.name.trim()) {
        errors.name = t("auth.login.validation.nameRequired");
      }

      const confirmError = validateConfirm(fields.confirm);

      if (confirmError) {
        errors.confirm = confirmError;
      }
    }

    setTouched({ email: true, password: true, name: true, confirm: true });
    setFieldErrors(errors);

    if (Object.keys(errors).length > 0) {
      if (errors.name) {
        nameRef.current?.focus();
      } else if (errors.email) {
        emailRef.current?.focus();
      } else if (errors.password) {
        passwordRef.current?.focus();
      } else if (errors.confirm) {
        confirmRef.current?.focus();
      }

      return;
    }

    setGeneralError(null);
    setPending(true);

    if (mode === "signin") {
      const result = await requestPasswordLogin({
        email: fields.email,
        password: fields.password,
      });

      if (result.ok) {
        const destination = next ?? "/painel";
        router.replace(destination);
        router.refresh();
        return;
      }

      setPending(false);
      setGeneralError({
        messageKey: result.messageKey,
        retryAfter: result.retryAfter,
        code: result.code,
      });

      if (result.code === "email_not_verified") {
        setPending(false);
        const params = new URLSearchParams({ email: fields.email });

        if (next) {
          params.set("next", next);
        }

        router.push(`/confirmar-email?${params.toString()}`);
      }

      return;
    }

    const result = await requestRegister({
      name: fields.name,
      email: fields.email,
      password: fields.password,
      acceptedTerms: accepted,
      acceptedPrivacy: accepted,
    });

    if (result.ok) {
      const params = new URLSearchParams({ email: fields.email });

      if (next) {
        params.set("next", next);
      }

      router.push(`/confirmar-email?${params.toString()}`);
      return;
    }

    setPending(false);
    setGeneralError({
      messageKey: result.messageKey,
      retryAfter: result.retryAfter,
      code: result.code,
    });
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

            {tabsVisible ? (
              <div
                role="tablist"
                aria-label={t("auth.login.tabsLabel")}
                onKeyDown={handleTabKeyDown}
                className="mb-8 grid grid-cols-2 gap-1 rounded-[6px] border border-border bg-surface p-1"
              >
                {availableModes.map((tabMode) => {
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
            ) : null}

            <div
              role={tabsVisible ? "tabpanel" : undefined}
              id={tabsVisible ? "login-panel" : undefined}
              aria-labelledby={tabsVisible ? `login-tab-${mode}` : undefined}
              className="min-h-[28rem]"
            >
              <h2 className="font-serif text-4xl leading-tight tracking-tight">{t(copy.title)}</h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {t(copy.subtitle)}
              </p>

              {generalError ? (
                <div
                  className="mt-6 rounded-[6px] border border-border bg-surface p-3"
                  role="alert"
                >
                  <p className="text-sm font-medium">{t("auth.login.errorTitle")}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {t(generalError.messageKey)}
                  </p>
                  {generalError.retryAfter ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {t("auth.login.blockedDescription", {
                        seconds: generalError.retryAfter,
                      })}
                    </p>
                  ) : null}
                </div>
              ) : null}

              <form
                key={mode}
                className="auth-form-enter mt-6 space-y-4"
                noValidate
                onSubmit={(event) => {
                  event.preventDefault();
                  void submitPasswordForm();
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
                    className="text-sm font-medium leading-relaxed text-foreground"
                  >
                    {t("auth.login.acceptError")}
                  </p>
                ) : fieldsLocked ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {t("auth.login.acceptToUnlock")}
                  </p>
                ) : null}

                <Button
                  type="button"
                  size="lg"
                  variant="outline"
                  aria-busy={googlePending}
                  onClick={startGoogleLogin}
                  className="h-12 w-full gap-3 border-border bg-surface text-foreground transition-[background-color,border-color] hover:bg-surface-elevated active:translate-y-px [&_svg]:size-5"
                >                  {googlePending ? (
                    <LoaderCircle className="animate-spin" aria-hidden="true" />
                  ) : (
                    <GoogleIcon className="size-5" />
                  )}
                  {googlePending ? t("auth.login.redirecting") : t(copy.google)}
                </Button>

                {copy.googleHint ? (
                  <p className="text-center text-xs leading-relaxed text-muted-foreground">
                    {t(copy.googleHint)}
                  </p>
                ) : null}

                {passwordFieldsVisible ? (
                  <>
                    <div className="flex items-center gap-3 pt-2 text-xs text-muted-foreground">
                      <span className="h-px flex-1 bg-border" aria-hidden="true" />
                      {t("auth.login.or")}
                      <span className="h-px flex-1 bg-border" aria-hidden="true" />
                    </div>

                    {mode === "signup" ? (
                      <FormField label={t("auth.login.fullName")} error={fieldErrors.name}>
                        {({ inputId, describedBy }) => (
                          <TextField
                            ref={nameRef}
                            id={inputId}
                            name="name"
                            type="text"
                            autoComplete="name"
                            value={fields.name}
                            disabled={pending || fieldsLocked}
                            invalid={Boolean(fieldErrors.name)}
                            aria-describedby={describedBy}
                            onChange={(event) => {
                              setFields((current) => ({
                                ...current,
                                name: event.target.value,
                              }));

                              if (touched.name) {
                                setFieldErrors((current) => ({
                                  ...current,
                                  name: event.target.value.trim()
                                    ? undefined
                                    : t("auth.login.validation.nameRequired"),
                                }));
                              }
                            }}
                            onBlur={() => {
                              setTouched((current) => ({ ...current, name: true }));
                              setFieldErrors((current) => ({
                                ...current,
                                name: fields.name.trim()
                                  ? undefined
                                  : t("auth.login.validation.nameRequired"),
                              }));
                            }}
                          />
                        )}
                      </FormField>
                    ) : null}

                    <FormField label={t("auth.login.email")} error={fieldErrors.email}>
                      {({ inputId, describedBy }) => (
                        <TextField
                          ref={emailRef}
                          id={inputId}
                          name="email"
                          type="email"
                          inputMode="email"
                          autoComplete="email"
                          placeholder={t("auth.login.emailPlaceholder")}
                          value={fields.email}
                          disabled={pending || fieldsLocked}
                          invalid={Boolean(fieldErrors.email)}
                          aria-describedby={describedBy}
                          onChange={(event) => {
                            setFields((current) => ({
                              ...current,
                              email: event.target.value,
                            }));

                            if (touched.email) {
                              setFieldErrors((current) => ({
                                ...current,
                                email: validateEmail(event.target.value),
                              }));
                            }
                          }}
                          onBlur={() => {
                            setTouched((current) => ({ ...current, email: true }));
                            setFieldErrors((current) => ({
                              ...current,
                              email: validateEmail(fields.email),
                            }));
                          }}
                        />
                      )}
                    </FormField>

                    <FormField label={t("auth.login.password")} error={fieldErrors.password}>
                      {({ inputId, describedBy }) => (
                        <PasswordField
                          ref={passwordRef}
                          id={inputId}
                          name="password"
                          autoComplete={mode === "signup" ? "new-password" : "current-password"}
                          value={fields.password}
                          disabled={pending || fieldsLocked}
                          invalid={Boolean(fieldErrors.password)}
                          aria-describedby={describedBy}
                          onChange={(event) => {
                            const value = event.target.value;
                            setFields((current) => ({ ...current, password: value }));

                            if (touched.password) {
                              setFieldErrors((current) => ({
                                ...current,
                                password: validatePasswordField(value),
                              }));
                            }

                            if (touched.confirm && fields.confirm) {
                              syncConfirmError(fields.confirm, value);
                            }
                          }}
                          onBlur={() => {
                            setTouched((current) => ({ ...current, password: true }));
                            setFieldErrors((current) => ({
                              ...current,
                              password: validatePasswordField(fields.password),
                            }));
                          }}
                        />
                      )}
                    </FormField>

                    {mode === "signin" ? (
                      <div className="-mt-1 flex justify-end">
                        {passwordResetEnabled ? (
                          <Link
                            href="/esqueci-senha"
                            className="inline-flex min-h-11 items-center text-sm text-muted-foreground underline decoration-border underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground"
                          >
                            {t("auth.login.forgotPassword")}
                          </Link>
                        ) : null}
                      </div>
                    ) : (
                      <div className="-mt-1">
                        {policy ? (
                          <PasswordStrengthMeter
                            value={fields.password}
                            policy={policy}
                            identifiers={identifiers}
                          />
                        ) : null}
                      </div>
                    )}

                    {mode === "signup" ? (
                      <FormField
                        label={t("auth.login.confirmPassword")}
                        error={
                          passwordMatch === "mismatch"
                            ? t("auth.login.validation.passwordMismatch")
                            : fieldErrors.confirm
                        }
                        errorTone="danger"
                      >
                        {({ inputId, describedBy }) => (
                          <PasswordField
                            ref={confirmRef}
                            id={inputId}
                            name="confirm-password"
                            autoComplete="new-password"
                            value={fields.confirm}
                            disabled={pending || fieldsLocked}
                            invalid={Boolean(fieldErrors.confirm) || passwordMatch === "mismatch"}
                            danger={passwordMatch === "mismatch"}
                            aria-describedby={describedBy}
                            onChange={(event) => {
                              const value = event.target.value;
                              setFields((current) => ({ ...current, confirm: value }));
                              syncConfirmError(value, fields.password);
                            }}
                            onBlur={() => {
                              setTouched((current) => ({ ...current, confirm: true }));
                              setFieldErrors((current) => ({
                                ...current,
                                confirm: validateConfirm(fields.confirm),
                              }));
                            }}
                          />
                        )}
                      </FormField>
                    ) : null}

                    <Button
                      type="submit"
                      size="lg"
                      aria-busy={pending}
                      className="h-12 w-full gap-2 bg-petrol-base text-on-petrol transition-[background-color,opacity] hover:bg-petrol-base/90 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {pending ? (
                        <LoaderCircle className="animate-spin" aria-hidden="true" />
                      ) : null}
                      {pending ? t(copy.submitting) : t(copy.submit)}
                    </Button>
                  </>
                ) : null}

                {generalError?.code === "email_not_verified" ? (
                  <div className="rounded-[6px] border border-border bg-surface p-3">
                    <p className="text-sm font-medium">{t("auth.login.unverifiedTitle")}</p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {t("auth.login.unverifiedDescription")}
                    </p>
                    <Link
                      href="/confirmar-email"
                      className="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
                    >
                      {t("auth.login.resend")}
                    </Link>
                  </div>
                ) : null}
              </form>

              {tabsVisible ? (
                <p className="mt-6 text-sm text-muted-foreground">
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
              ) : null}

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
