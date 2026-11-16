"use client";

import { ArrowUpRight, FileText, HardDrive, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import type { PrivacyContact } from "@/lib/site/privacy";

export function PrivacySection({ contact }: Readonly<{ contact: PrivacyContact }>) {
  const { t } = useI18n();
  const hasUrl = contact.url !== null;
  const hasEmail = contact.email !== null;
  const contactHref =
    contact.href.startsWith("mailto:") && contact.email
      ? `${contact.href}?subject=${encodeURIComponent(t("account.privacy.title"))}`
      : contact.href;
  const external = contactHref.startsWith("http");
  const contactLabel = hasUrl
    ? t("account.privacy.contactUrl")
    : hasEmail
      ? t("account.privacy.contactEmail", { email: contact.email ?? "" })
      : t("account.privacy.contactSupport");

  return (
    <section aria-labelledby="account-privacy-title">
      <h2
        id="account-privacy-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.privacy.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/70">
        {t("account.privacy.description")}
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {[
          { label: t("account.privacy.documents"), icon: FileText },
          { label: t("account.privacy.storage"), icon: HardDrive },
        ].map((item) => {
          const Icon = item.icon;

          return (
            <div key={item.label} className="rounded-[6px] border border-border bg-card p-4">
              <p className="flex items-center gap-2 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70">
                <Icon className="size-3.5" aria-hidden="true" />
                {item.label}
              </p>
              <p className="mt-1 text-sm text-foreground/70">{t("account.privacy.unavailable")}</p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 flex items-start gap-2 text-[0.65rem] leading-relaxed text-foreground/70">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span>{t("account.privacy.usageGap")}</span>
      </p>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-[6px] border border-border bg-card p-5">
          <h3 className="text-sm font-medium">{t("account.privacy.exportTitle")}</h3>
          <p className="mt-1 text-xs leading-relaxed text-foreground/70">
            {t("account.privacy.exportDescription")}
          </p>
          <Button asChild variant="outline" size="sm" className="mt-4">
            <a href={contactHref} {...(external ? { target: "_blank", rel: "noreferrer" } : {})}>
              {t("account.privacy.exportAction")}
              <ArrowUpRight aria-hidden="true" />
            </a>
          </Button>
        </div>

        <div className="rounded-[6px] border border-border bg-card p-5">
          <h3 className="text-sm font-medium">{t("account.privacy.contact")}</h3>
          <p className="mt-1 break-all text-xs leading-relaxed text-foreground/70">
            {hasUrl ? contact.url : hasEmail ? contact.email : t("account.privacy.contactFallback")}
          </p>
          <Button asChild variant="outline" size="sm" className="mt-4">
            <a href={contactHref} {...(external ? { target: "_blank", rel: "noreferrer" } : {})}>
              {contactLabel}
              <ArrowUpRight aria-hidden="true" />
            </a>
          </Button>
          {hasUrl && hasEmail ? (
            <p className="mt-3 text-[0.65rem] text-foreground/70">
              <a
                className="underline underline-offset-4 hover:text-foreground"
                href={`mailto:${contact.email}?subject=${encodeURIComponent(
                  t("account.privacy.title"),
                )}`}
              >
                {t("account.privacy.contactEmail", { email: contact.email ?? "" })}
              </a>
            </p>
          ) : null}
        </div>
      </div>

      <p className="mt-4 text-[0.65rem] leading-relaxed text-foreground/70">
        {t("account.privacy.lgpd")}
      </p>
    </section>
  );
}
