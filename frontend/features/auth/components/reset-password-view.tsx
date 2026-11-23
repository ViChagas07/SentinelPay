"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AuthNotice, AuthShell, SubmitButton } from "@/features/auth/components/auth-shell";
import { FormField, PasswordField } from "@/features/auth/components/form-fields";
import { PasswordStrengthMeter } from "@/features/auth/components/password-strength-meter";
import type { PasswordPolicy } from "@/lib/auth/capabilities";
import { requestPasswordReset } from "@/lib/auth/client";
import { identifierFragments, passwordIssues } from "@/lib/auth/password";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

export type ResetPasswordViewProps = {
  token: string | null;
  policy: PasswordPolicy;
};

export function ResetPasswordView({ token, policy }: Readonly<ResetPasswordViewProps>) {
  const { t } = useI18n();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorKey, setErrorKey] = useState<TranslationKey | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirm?: string }>({});
  const passwordRef = useRef<HTMLInputElement | null>(null);
  const confirmRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (token) {
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      window.history.replaceState(null, "", url.pathname + url.search);
    }
  }, [token]);

  if (!token) {
    return (
      <AuthShell title={t("auth.reset.invalidTitle")}>
        <div className="space-y-5">
          <AuthNotice
            tone="error"
            title={t("auth.reset.invalidTitle")}
            description={t("auth.reset.invalidDescription")}
          />
          <Link
            href="/esqueci-senha"
            className="inline-flex min-h-11 items-center text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {t("auth.reset.requestNew")}
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (success) {
    return (
      <AuthShell title={t("auth.reset.successTitle")}>
        <div className="space-y-5">
          <AuthNotice
            tone="success"
            title={t("auth.reset.successTitle")}
            description={t("auth.reset.successDescription")}
          />
          <Link
            href="/login"
            className="inline-flex min-h-11 items-center text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {t("auth.verify.goToLogin")}
          </Link>
        </div>
      </AuthShell>
    );
  }

  const identifiers: string[] = identifierFragments("", "");

  async function submit(): Promise<void> {
    if (pending || !token) {
      return;
    }

    const errors: { password?: string; confirm?: string } = {};

    if (!password) {
      errors.password = t("auth.login.validation.passwordRequired");
    } else if (passwordIssues(password, policy, identifiers).length > 0) {
      errors.password = t("auth.login.validation.passwordPolicy");
    }

    if (!confirm) {
      errors.confirm = t("auth.login.validation.confirmRequired");
    } else if (confirm !== password) {
      errors.confirm = t("auth.login.validation.passwordMismatch");
    }

    setFieldErrors(errors);

    if (errors.password) {
      passwordRef.current?.focus();
      return;
    }

    if (errors.confirm) {
      confirmRef.current?.focus();
      return;
    }

    setErrorKey(null);
    setPending(true);
    const result = await requestPasswordReset({ token, password });
    setPending(false);

    if (result.ok) {
      setSuccess(true);
      return;
    }

    setErrorKey(result.messageKey);
  }

  return (
    <AuthShell title={t("auth.reset.title")} subtitle={t("auth.reset.subtitle")}>
      <form
        noValidate
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        {errorKey ? (
          <AuthNotice tone="error" title={t("auth.login.errorTitle")} description={t(errorKey)} />
        ) : null}

        <div className="space-y-2">
          <FormField label={t("auth.login.password")} error={fieldErrors.password}>
            {({ inputId, describedBy }) => (
              <PasswordField
                ref={passwordRef}
                id={inputId}
                name="password"
                autoComplete="new-password"
                value={password}
                disabled={pending}
                invalid={Boolean(fieldErrors.password)}
                aria-describedby={describedBy}
                onChange={(event) => setPassword(event.target.value)}
                onBlur={() => {
                  if (!password) {
                    setFieldErrors((current) => ({
                      ...current,
                      password: t("auth.login.validation.passwordRequired"),
                    }));
                    return;
                  }

                  setFieldErrors((current) => ({
                    ...current,
                    password:
                      passwordIssues(password, policy, identifiers).length > 0
                        ? t("auth.login.validation.passwordPolicy")
                        : undefined,
                  }));
                }}
              />
            )}
          </FormField>
          <PasswordStrengthMeter value={password} policy={policy} identifiers={identifiers} />
        </div>

        <FormField label={t("auth.login.confirmPassword")} error={fieldErrors.confirm}>
          {({ inputId, describedBy }) => (
            <PasswordField
              ref={confirmRef}
              id={inputId}
              name="confirm-password"
              autoComplete="new-password"
              value={confirm}
              disabled={pending}
              invalid={Boolean(fieldErrors.confirm)}
              aria-describedby={describedBy}
              onChange={(event) => {
                setConfirm(event.target.value);
                setFieldErrors((current) => ({
                  ...current,
                  confirm:
                    event.target.value === password
                      ? undefined
                      : t("auth.login.validation.passwordMismatch"),
                }));
              }}
              onBlur={() => {
                setFieldErrors((current) => ({
                  ...current,
                  confirm: !confirm
                    ? t("auth.login.validation.confirmRequired")
                    : confirm === password
                      ? undefined
                      : t("auth.login.validation.passwordMismatch"),
                }));
              }}
            />
          )}
        </FormField>

        <p className="text-xs leading-relaxed text-muted-foreground">{t("auth.reset.sessions")}</p>

        <SubmitButton
          pending={pending}
          label={t("auth.reset.submit")}
          pendingLabel={t("auth.reset.submitting")}
        />
      </form>
    </AuthShell>
  );
}
