"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { FormField, TextField } from "@/features/auth/components/form-fields";
import { AuthNotice, AuthShell, SubmitButton } from "@/features/auth/components/auth-shell";
import { requestPasswordForgot } from "@/lib/auth/client";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

export function ForgotPasswordView() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [errorKey, setErrorKey] = useState<TranslationKey | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>(undefined);
  const emailRef = useRef<HTMLInputElement | null>(null);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (countdown <= 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      setCountdown((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [countdown]);

  async function submit(): Promise<void> {
    if (pending) {
      return;
    }

    if (!email.trim()) {
      setFieldError(t("auth.login.validation.emailRequired"));
      emailRef.current?.focus();
      return;
    }

    setFieldError(undefined);
    setErrorKey(null);
    setPending(true);
    const result = await requestPasswordForgot(email);
    setPending(false);

    if (result.ok) {
      setDone(true);
      return;
    }

    setErrorKey(result.messageKey);
    setRetryAfter(result.retryAfter ?? null);

    if (result.retryAfter) {
      setCountdown(result.retryAfter);
    }
  }

  return (
    <AuthShell
      title={t("auth.forgot.title")}
      subtitle={t("auth.forgot.subtitle")}
      footer={
        <Link
          href="/login"
          className="inline-flex min-h-11 items-center text-sm text-muted-foreground underline decoration-border underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground"
        >
          {t("auth.forgot.backToLogin")}
        </Link>
      }
    >
      {done ? (
        <div className="space-y-4">
          <AuthNotice
            tone="success"
            title={t("auth.forgot.title")}
            description={t("auth.forgot.neutral")}
          />
          <Link
            href="/login"
            className="inline-flex min-h-11 items-center text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {t("auth.forgot.backToLogin")}
          </Link>
        </div>
      ) : (
        <form
          noValidate
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {errorKey ? (
            <AuthNotice
              tone="error"
              title={t("auth.login.errorTitle")}
              description={
                retryAfter !== null
                  ? t("auth.login.blockedDescription", { seconds: countdown })
                  : t(errorKey)
              }
            />
          ) : null}

          <FormField label={t("auth.login.email")} error={fieldError}>
            {({ inputId, describedBy }) => (
              <TextField
                ref={emailRef}
                id={inputId}
                name="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder={t("auth.login.emailPlaceholder")}
                value={email}
                disabled={pending}
                invalid={Boolean(fieldError)}
                aria-describedby={describedBy}
                onChange={(event) => setEmail(event.target.value)}
                onBlur={() => {
                  setFieldError(
                    email.trim() ? undefined : t("auth.login.validation.emailRequired"),
                  );
                }}
              />
            )}
          </FormField>

          <SubmitButton
            pending={pending}
            label={t("auth.forgot.submit")}
            pendingLabel={t("auth.forgot.submitting")}
          />
        </form>
      )}
    </AuthShell>
  );
}
