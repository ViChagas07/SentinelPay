"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { configureApiInterceptors, isApiError } from "@/lib/api";
import type { ApiError } from "@/lib/api/errors";
import { useI18n } from "@/lib/i18n/provider";
import { buildLoginPath } from "@/lib/session/client";
import { SESSION_EXPIRED_CODE, SESSION_EXPIRED_REASON } from "@/lib/session/constants";

function rateLimitDescription(
  error: ApiError,
  t: ReturnType<typeof useI18n>["t"],
): { description: string; duration: number } {
  if (error.retryAfterSeconds !== null) {
    return {
      description: t("errors.rateLimited.retryAfter", { seconds: error.retryAfterSeconds }),
      duration: Math.max(6_000, error.retryAfterSeconds * 1_000 + 2_000),
    };
  }

  return {
    description: t("errors.rateLimited.description"),
    duration: 6_000,
  };
}

export function SessionGuard() {
  const router = useRouter();
  const { t } = useI18n();

  useEffect(() => {
    configureApiInterceptors({
      onUnauthorized: (error) => {
        const nextPath = `${window.location.pathname}${window.location.search}`;
        const expired = error.code === SESSION_EXPIRED_CODE;
        router.replace(
          buildLoginPath({
            next: nextPath.startsWith("/") ? nextPath : undefined,
            reason: expired ? SESSION_EXPIRED_REASON : undefined,
            code: expired ? undefined : error.code,
          }),
        );
      },
      onForbidden: (error) => {
        if (!isApiError(error)) {
          return;
        }

        router.replace(buildLoginPath({ reason: "forbidden", code: "forbidden" }));
      },
      onRateLimited: (error) => {
        const notice = rateLimitDescription(error, t);
        toast.warning(t("errors.rateLimited.title"), {
          id: "api-rate-limit",
          description: notice.description,
          duration: notice.duration,
        });
      },
    });

    return () => configureApiInterceptors({});
  }, [router, t]);

  return null;
}
