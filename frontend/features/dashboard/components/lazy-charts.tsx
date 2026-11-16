"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

export const LazyStripChart = dynamic(
  () => import("@/components/ui/strip-chart").then((module) => module.StripChart),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[200px] w-full" />,
  },
);

export const LazySparkline = dynamic(
  () => import("@/components/ui/sparkline").then((module) => module.Sparkline),
  {
    ssr: false,
    loading: () => <Skeleton className="h-7 w-24 shrink-0" />,
  },
);
