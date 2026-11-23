"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { BACK_FALLBACK_PATH, resolveBackNavigationAction } from "@/lib/session/back-navigation";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const FALLBACK_DELAY_MS = 500;

export type BackButtonProps = {
  className?: string;
  tone?: "default" | "onPetrol";
};

export function BackButton({ className, tone = "default" }: BackButtonProps) {
  const { t } = useI18n();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, []);

  function goBack() {
    if (pending) {
      return;
    }

    if (resolveBackNavigationAction(window.history.length) === "fallback") {
      router.replace(BACK_FALLBACK_PATH);
      return;
    }

    setPending(true);

    function handlePopState(): void {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }

      setPending(false);
    }

    window.addEventListener("popstate", handlePopState, { once: true });
    router.back();

    timeoutRef.current = window.setTimeout(() => {
      timeoutRef.current = null;
      setPending(false);
      router.replace(BACK_FALLBACK_PATH);
    }, FALLBACK_DELAY_MS);
  }

  return (
    <Button
      type="button"
      variant="ghost"
      onClick={goBack}
      aria-label={t("auth.login.back")}
      className={cn(
        "-ml-2 min-h-11 gap-2 px-2 text-sm",
        tone === "onPetrol"
          ? "text-on-petrol/80 hover:bg-on-petrol/10 hover:text-on-petrol focus-visible:ring-on-petrol"
          : "text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      <ArrowLeft aria-hidden="true" />
      {t("auth.login.back")}
    </Button>
  );
}
