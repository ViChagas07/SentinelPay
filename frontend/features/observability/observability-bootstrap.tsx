"use client";

import { useEffect } from "react";

import { initObservability, observabilityConfigured } from "@/lib/observability/sentry";

export function ObservabilityBootstrap() {
  useEffect(() => {
    if (!observabilityConfigured()) {
      return;
    }

    void initObservability();
  }, []);

  return null;
}
