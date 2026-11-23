"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AuthNotice, AuthShell } from "@/features/auth/components/auth-shell";
import { FormField, TextField } from "@/features/auth/components/form-fields";
import { requestVerificationResend } from "@/lib/auth/client";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

export type ConfirmEmailViewProps = {
  initialEmail: string | null;
};

const RESEND_COOLDOWN_SECONDS = 60;

export function ConfirmEmailView({ initialEmail }: Readonly<ConfirmEmailViewProps>) {
  const { t } = useI18n();
  const [email, setEmail] = useState(initialEmail ?? "");
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [errorKey, setErrorKey] = useState<TranslationKey | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>(undefined);
  const emailRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (cooldown <= 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      setCooldown((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function resend(): Promise<void> {
    if (pending || cooldown > 0) {
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
    const result = await requestVerificationResend(email);
    setPending(false);

    if (result.ok) {
      setSent(true);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      return;
    }

    setErrorKey(result.messageKey);

    if (result.retryAfter) {
      setCooldown(result.retryAfter);
    }
  }

  return (
    <AuthShell
      title={t("auth.confirm.title")}
      subtitle={t("auth.confirm.subtitle")}
      footer={
        <Link
          href="/login"
          className="inline-flex min-h-11 items-center text-sm text-muted-foreground underline decoration-border underline-offset-4 transition-colors hover:text-foreground hover:decoration-foreground"
        >
          {t("auth.verify.goToLogin")}
        </Link>
      }
    >
      <div className="space-y-5">
        {errorKey ? (
          <AuthNotice tone="error" title={t("auth.login.errorTitle")} description={t(errorKey)} />
        ) : null}

        {sent ? (
          <AuthNotice
            tone="success"
            title={t("auth.confirm.resend")}
            description={t("auth.confirm.sent")}
          />
        ) : null}

        <form
          noValidate
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            void resend();
          }}
        >
          <FormField label={t("auth.confirm.emailLabel")} error={fieldError}>
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
                disabled={pending || cooldown > 0}
                invalid={Boolean(fieldError)}
                aria-describedby={describedBy}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setSent(false);
                }}
                onBlur={() => {
                  setFieldError(
                    email.trim() ? undefined : t("auth.login.validation.emailRequired"),
                  );
                }}
              />
            )}
          </FormField>

          <button
            type="submit"
            disabled={pending || cooldown > 0}
            className="inline-flex h-12 w-full items-center justify-center rounded-[6px] bg-petrol-base px-6 text-sm font-medium text-on-petrol transition-colors hover:bg-petrol-base/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending
              ? t("auth.confirm.resending")
              : cooldown > 0
                ? t("auth.confirm.wait", { seconds: cooldown })
                : t("auth.confirm.resend")}
          </button>
        </form>
      </div>
    </AuthShell>
  );
}
