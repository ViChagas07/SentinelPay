"use client";

import { Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { UserProfile } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";

export function OrganizationSection({ user }: Readonly<{ user: UserProfile }>) {
  const { t } = useI18n();
  const roleKey = user.role === "admin" ? "account.role.admin" : "account.role.user";

  return (
    <section aria-labelledby="account-organization-title">
      <h2
        id="account-organization-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.organization.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/70">
        {t("account.organization.description")}
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-[6px] border border-border bg-card p-4">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
            {t("account.organization.name")}
          </p>
          <p className="mt-1 text-sm text-foreground/70">{t("account.organization.unavailable")}</p>
        </div>
        <div className="rounded-[6px] border border-border bg-card p-4">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
            {t("account.organization.plan")}
          </p>
          <p className="mt-1 text-sm text-foreground/70">{t("account.organization.unavailable")}</p>
        </div>
        <div className="rounded-[6px] border border-border bg-card p-4">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
            {t("account.organization.role")}
          </p>
          <p className="mt-1">
            <Badge variant="outline">{t(roleKey)}</Badge>
          </p>
        </div>
        <div className="rounded-[6px] border border-border bg-card p-4">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
            {t("account.organization.members")}
          </p>
          <p className="mt-1 text-sm text-foreground/70">{t("account.organization.unavailable")}</p>
        </div>
      </div>

      <p className="mt-4 flex items-start gap-2 text-[0.65rem] leading-relaxed text-foreground/70">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span>{t("account.organization.gap")}</span>
      </p>
    </section>
  );
}
