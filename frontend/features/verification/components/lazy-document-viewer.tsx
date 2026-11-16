"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

import type { DocumentViewerProps } from "./document-viewer";

const DocumentViewerDynamic = dynamic(
  () => import("./document-viewer").then((module) => module.DocumentViewer),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-[6px] border border-border bg-surface p-3" aria-hidden="true">
        <Skeleton className="h-80 w-full" />
      </div>
    ),
  },
);

export function LazyDocumentViewer(props: DocumentViewerProps) {
  return <DocumentViewerDynamic {...props} />;
}
