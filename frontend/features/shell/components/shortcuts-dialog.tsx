"use client";

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
import { useI18n } from "@/lib/i18n/provider";

function Kbd({ children }: Readonly<{ children: string }>) {
  return (
    <kbd className="inline-flex min-w-6 items-center justify-center rounded-[4px] border border-border bg-surface-elevated px-1.5 py-0.5 font-mono text-[0.65rem] text-foreground">
      {children}
    </kbd>
  );
}

export type ShortcutsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function ShortcutsDialog({ open, onOpenChange }: ShortcutsDialogProps) {
  const { t } = useI18n();
  const rows = [
    { keys: ["g", "p"], label: t("shell.shortcuts.panel") },
    { keys: ["g", "v"], label: t("shell.shortcuts.verification") },
    { keys: ["n"], label: t("shell.shortcuts.newVerification") },
    { keys: ["?"], label: t("shell.shortcuts.help") },
    { keys: ["Ctrl", "K"], label: t("shell.shortcuts.command") },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("shell.shortcuts.title")}</DialogTitle>
          <DialogDescription>{t("shell.shortcuts.description")}</DialogDescription>
        </DialogHeader>
        <dl className="divide-y divide-border border-y border-border">
          {rows.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-sm text-muted-foreground">{row.label}</dt>
              <dd className="flex items-center gap-1">
                {row.keys.map((key, index) => (
                  <span key={`${row.label}-${key}`} className="flex items-center gap-1">
                    {index > 0 ? <span className="text-xs text-muted-foreground">+</span> : null}
                    <Kbd>{key}</Kbd>
                  </span>
                ))}
              </dd>
            </div>
          ))}
        </dl>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {t("shell.shortcuts.close")}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
