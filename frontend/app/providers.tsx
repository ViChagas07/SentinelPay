"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { Toaster } from "@/components/ui/sonner";
import { SessionGuard } from "@/features/auth/components/session-guard";
import { ObservabilityBootstrap } from "@/features/observability/observability-bootstrap";
import type { Locale } from "@/lib/i18n";
import { I18nProvider } from "@/lib/i18n/provider";
import type { DateFormat } from "@/lib/preferences/date-format";
import { createQueryClient } from "@/lib/query/client";
import type { ThemeMode } from "@/lib/theme/constants";
import { ThemeProvider } from "@/lib/theme/provider";

export function Providers({
  initialLocale,
  initialTheme,
  initialDateFormat,
  children,
}: Readonly<{
  initialLocale: Locale;
  initialTheme: ThemeMode;
  initialDateFormat: DateFormat;
  children: ReactNode;
}>) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider initialLocale={initialLocale} initialDateFormat={initialDateFormat}>
        <ThemeProvider initialMode={initialTheme}>
          <SessionGuard />
          <ObservabilityBootstrap />
          {children}
          <Toaster />
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
