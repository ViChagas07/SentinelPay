"use client";

import { CircleAlert, CircleCheck, Info, LoaderCircle, TriangleAlert, X } from "lucide-react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

import { useI18n } from "@/lib/i18n/provider";
import { useTheme } from "@/lib/theme/provider";

function Toaster(props: ToasterProps) {
  const { mode } = useTheme();
  const { t } = useI18n();

  return (
    <Sonner
      theme={mode === "system" ? "system" : mode}
      position="bottom-right"
      closeButton
      richColors={false}
      containerAriaLabel={t("design.toast.region")}
      icons={{
        success: <CircleCheck className="size-4" aria-hidden="true" />,
        info: <Info className="size-4" aria-hidden="true" />,
        warning: <TriangleAlert className="size-4" aria-hidden="true" />,
        error: <CircleAlert className="size-4" aria-hidden="true" />,
        loading: <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />,
        close: <X className="size-4" aria-hidden="true" />,
      }}
      toastOptions={{
        closeButtonAriaLabel: t("common.close"),
        classNames: {
          toast: "rounded-[6px] border border-border bg-surface text-foreground shadow-none",
          title: "text-sm font-medium",
          description: "text-sm text-muted-foreground",
          actionButton: "rounded-[6px] bg-primary text-primary-foreground",
          cancelButton: "rounded-[6px] border border-border bg-transparent text-foreground",
          closeButton: "border border-border bg-surface text-foreground",
          icon: "text-foreground",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
