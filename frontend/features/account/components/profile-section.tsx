"use client";

import { BadgeCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { UserProfile } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";

import { UserAvatar } from "@/features/shell/components/user-avatar";

export function ProfileSection({ user }: Readonly<{ user: UserProfile }>) {
  const { t } = useI18n();

  return (
    <section aria-labelledby="account-profile-title">
      <h2
        id="account-profile-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.profile.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/70">
        {t("account.profile.description")}
      </p>

      <div className="mt-5 rounded-[6px] border border-border bg-card p-5 sm:p-6">
        <div className="flex flex-wrap items-start gap-4">
          <UserAvatar name={user.name} email={user.email} className="size-16 text-lg" />
          <div className="min-w-0">
            <p className="text-lg font-medium">{user.name?.trim() || user.email}</p>
            <p className="mt-0.5 break-all text-sm text-foreground/70">{user.email}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge variant="outline" className="gap-1.5">
                <BadgeCheck className="size-3" aria-hidden="true" />
                {t("account.managedByGoogle")}
              </Badge>
              <Badge variant="secondary">{t("account.profile.readOnly")}</Badge>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label
              htmlFor="account-profile-name"
              className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70"
            >
              {t("account.profile.name")}
            </label>
            <input
              id="account-profile-name"
              type="text"
              value={user.name ?? ""}
              readOnly
              placeholder={t("account.profile.nameNotInformed")}
              aria-describedby="account-profile-name-note"
              className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-foreground/70 focus-visible:ring-2 focus-visible:ring-ring"
            />
            <p
              id="account-profile-name-note"
              className="text-[0.65rem] leading-relaxed text-foreground/70"
            >
              {t("account.profile.nameGap")}
            </p>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="account-profile-email"
              className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70"
            >
              {t("account.profile.email")}
            </label>
            <input
              id="account-profile-email"
              type="email"
              value={user.email}
              readOnly
              aria-describedby="account-profile-email-note"
              className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <p
              id="account-profile-email-note"
              className="text-[0.65rem] leading-relaxed text-foreground/70"
            >
              {t("account.profile.emailManaged")}
            </p>
          </div>
        </div>

        <p className="mt-5 border-t border-border pt-4 text-[0.65rem] leading-relaxed text-foreground/70">
          {t("account.profile.avatarNote")}
        </p>
      </div>
    </section>
  );
}
