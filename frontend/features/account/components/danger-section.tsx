"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowUpRight, Info, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { buildDeleteAccountSchema, type DeleteAccountValues } from "@/lib/account/delete-form";
import { useUnsavedChangesWarning } from "@/lib/account/use-unsaved-changes-warning";
import { useI18n } from "@/lib/i18n/provider";
import type { PrivacyContact } from "@/lib/site/privacy";
import { cn } from "@/lib/utils";

type DeleteAccountDialogProps = {
  contact: PrivacyContact;
  onClose: () => void;
};

function DeleteAccountDialog({ contact, onClose }: DeleteAccountDialogProps) {
  const { t } = useI18n();
  const word = t("account.danger.confirmWord");
  const schema = useMemo(() => buildDeleteAccountSchema(word), [word]);
  const form = useForm<DeleteAccountValues>({
    resolver: zodResolver(schema),
    defaultValues: { confirmation: "" },
    mode: "onChange",
  });
  const confirmation = useWatch({ control: form.control, name: "confirmation" });
  const [requested, setRequested] = useState(false);
  const contactRef = useRef<HTMLAnchorElement | null>(null);
  useUnsavedChangesWarning(confirmation.trim().length > 0 && !requested);

  useEffect(() => {
    if (requested) {
      contactRef.current?.focus();
    }
  }, [requested]);

  const contactHref =
    contact.href.startsWith("mailto:") && contact.email
      ? `${contact.href}?subject=${encodeURIComponent(t("account.danger.dialogTitle"))}`
      : contact.href;
  const external = contactHref.startsWith("http");
  const contactLabel = contact.isFallback
    ? t("account.danger.supportAction")
    : contact.email && !contact.url
      ? t("account.privacy.contactEmail", { email: contact.email })
      : t("account.danger.contactAction");

  return (
    <Dialog open onOpenChange={(nextOpen) => (nextOpen ? undefined : onClose())}>
      <DialogContent
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          form.setFocus("confirmation");
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("account.danger.dialogTitle")}</DialogTitle>
          <DialogDescription className="text-foreground/70">
            {t("account.danger.dialogDescription")}
          </DialogDescription>
        </DialogHeader>

        {requested ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-[6px] border border-border bg-surface p-4">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium">{t("account.danger.requestedTitle")}</p>
                <p className="mt-1 text-xs leading-relaxed text-foreground/70">
                  {t("account.danger.requestedDescription")}
                </p>
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  {t("account.danger.close")}
                </Button>
              </DialogClose>
              <Button asChild>
                <a
                  ref={contactRef}
                  href={contactHref}
                  {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
                >
                  {contactLabel}
                  <ArrowUpRight aria-hidden="true" />
                </a>
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form
            onSubmit={form.handleSubmit(
              () => {
                setRequested(true);
                toast.success(t("account.danger.requestedToast"));
              },
              () => {
                toast.error(t("account.danger.confirmError", { word }));
              },
            )}
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <label htmlFor="account-delete-confirmation" className="text-sm font-medium">
                {t("account.danger.confirmLabel", { word })}
              </label>
              <input
                id="account-delete-confirmation"
                type="text"
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                aria-invalid={Boolean(form.formState.errors.confirmation)}
                aria-describedby={
                  form.formState.errors.confirmation
                    ? "account-delete-confirmation-error"
                    : "account-delete-confirmation-hint"
                }
                className={cn(
                  "h-9 w-full rounded-[6px] border bg-surface px-3 font-mono text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  form.formState.errors.confirmation ? "border-risk-high/60" : "border-border",
                )}
                {...form.register("confirmation")}
              />
              {form.formState.errors.confirmation ? (
                <p id="account-delete-confirmation-error" className="text-xs text-risk-high">
                  {t("account.danger.confirmError", { word })}
                </p>
              ) : (
                <p
                  id="account-delete-confirmation-hint"
                  className="text-[0.65rem] leading-relaxed text-foreground/70"
                >
                  {confirmation.trim().length > 0
                    ? t("account.danger.unsaved")
                    : t("account.danger.confirmHint")}
                </p>
              )}
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  {t("account.danger.cancel")}
                </Button>
              </DialogClose>
              <Button type="submit">{t("account.danger.submit")}</Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function DangerSection({ contact }: Readonly<{ contact: PrivacyContact }>) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  function closeDialog(): void {
    setOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  }

  return (
    <section aria-labelledby="account-danger-title">
      <h2
        id="account-danger-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.danger.title")}
      </h2>

      <div className="mt-5 rounded-[6px] border border-risk-high/40 bg-risk-high/5 p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <TriangleAlert className="mt-0.5 size-5 shrink-0 text-risk-high" aria-hidden="true" />
          <div className="min-w-0">
            <p className="max-w-2xl text-sm leading-relaxed text-foreground/70">
              {t("account.danger.description")}
            </p>
            <Button
              ref={triggerRef}
              type="button"
              variant="outline"
              className="mt-4 border-risk-high/40"
              onClick={() => setOpen(true)}
            >
              <TriangleAlert className="text-risk-high" aria-hidden="true" />
              {t("account.danger.button")}
            </Button>
          </div>
        </div>
      </div>

      <p className="mt-3 flex items-start gap-2 text-[0.65rem] leading-relaxed text-foreground/70">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        <span>{t("account.danger.unavailable")}</span>
      </p>

      {open ? <DeleteAccountDialog contact={contact} onClose={closeDialog} /> : null}
    </section>
  );
}
