"use client";

import { Info, LogOut, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/hooks/use-auth";
import { useI18n } from "@/lib/i18n/provider";

export function SecuritySection({
  sessionExpiresAt,
}: Readonly<{ sessionExpiresAt: number | null }>) {
  const { t, formatDate } = useI18n();
  const logout = useLogout();
  const expiry =
    sessionExpiresAt !== null && Number.isFinite(sessionExpiresAt)
      ? formatDate(new Date(sessionExpiresAt), {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : null;

  return (
    <section aria-labelledby="account-security-title">
      <h2
        id="account-security-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.security.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/70">
        {t("account.security.description")}
      </p>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-[6px] border border-border bg-card p-5">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
            {t("account.security.provider")}
          </p>
          <p className="mt-2 flex items-center gap-2 text-sm font-medium">
            <ShieldCheck className="size-4" aria-hidden="true" />
            {t("account.security.providerValue")}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-foreground/70">
            {t("account.security.providerNote")}
          </p>
        </div>

        <div className="rounded-[6px] border border-border bg-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
              {t("account.security.session")}
            </p>
            <Badge variant="petrol">{t("account.security.sessionActive")}</Badge>
          </div>
          <p className="mt-2 text-sm">
            {expiry
              ? t("account.security.expiresAt", { date: expiry })
              : t("account.security.expiryUnavailable")}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-foreground/70">
            {t("account.security.startUnavailable")}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-foreground/70">
            {t("account.security.otherSessions")}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
        >
          <LogOut aria-hidden="true" />
          {logout.isPending ? t("auth.logout.loading") : t("account.security.logoutCurrent")}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled
          title={t("account.security.logoutAllUnavailable")}
        >
          <LogOut aria-hidden="true" />
          {t("account.security.logoutAll")}
        </Button>
      </div>
      <p className="mt-3 flex items-start gap-2 text-[0.65rem] leading-relaxed text-foreground/70">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span>{t("account.security.logoutAllUnavailable")}</span>
      </p>
    </section>
  );
}
