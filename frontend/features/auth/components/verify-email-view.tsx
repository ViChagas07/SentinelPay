"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AuthNotice, AuthShell } from "@/features/auth/components/auth-shell";
import { requestEmailVerification } from "@/lib/auth/client";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

export type VerifyEmailViewProps = {
  token: string | null;
};

type Status = "idle" | "pending" | "success" | "error";

export function VerifyEmailView({ token }: Readonly<VerifyEmailViewProps>) {
  const { t } = useI18n();
  const [status, setStatus] = useState<Status>(token ? "pending" : "error");
  const [errorKey, setErrorKey] = useState<TranslationKey | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState(null, "", url.pathname + url.search);
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }

    let active = true;

    requestEmailVerification(token)
      .then((result) => {
        if (!active) {
          return;
        }

        if (result.ok) {
          setStatus("success");
          return;
        }

        setErrorKey(result.messageKey);
        setStatus("error");
      })
      .catch(() => {
        if (active) {
          setStatus("error");
        }
      });

    return () => {
      active = false;
    };
  }, [token]);

  return (
    <AuthShell title={t("auth.verify.title")}>
      <div className="space-y-5">
        {status === "pending" ? (
          <p className="text-sm leading-relaxed text-muted-foreground" role="status">
            {t("auth.verify.loading")}
          </p>
        ) : null}

        {status === "success" ? (
          <>
            <AuthNotice
              tone="success"
              title={t("auth.verify.successTitle")}
              description={t("auth.verify.successDescription")}
            />
            <Link
              href="/login"
              className="inline-flex min-h-11 items-center text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
            >
              {t("auth.verify.goToLogin")}
            </Link>
          </>
        ) : null}

        {status === "error" ? (
          <>
            <AuthNotice
              tone="error"
              title={t("auth.verify.errorTitle")}
              description={errorKey ? t(errorKey) : t("auth.verify.errorDescription")}
            />
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t("auth.verify.resendHint")}
            </p>
            <Link
              href="/confirmar-email"
              className="inline-flex min-h-11 items-center text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
            >
              {t("auth.verify.resendLabel")}
            </Link>
            <Link
              href="/login"
              className="inline-flex min-h-11 items-center text-sm text-muted-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
            >
              {t("auth.verify.goToLogin")}
            </Link>
          </>
        ) : null}
      </div>
    </AuthShell>
  );
}
