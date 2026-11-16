"use client";

import { ExternalLink, Minus, Plus, RotateCcw } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import { detectFileKind } from "@/lib/verification/upload";
import { cn } from "@/lib/utils";

export type DocumentViewerProps = {
  file: File | null;
  scanning?: boolean;
  className?: string;
  emptyTitle?: string;
  emptyDescription?: string;
};

const ZOOM_STEP = 25;
const MIN_ZOOM = 50;
const MAX_ZOOM = 300;

function ScanLine() {
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <motion.div
        className="absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-petrol-500/25 to-transparent"
        initial={{ top: "6%" }}
        animate={reduceMotion ? { top: "18%" } : { top: ["6%", "88%"] }}
        transition={
          reduceMotion
            ? { duration: 0 }
            : { duration: 2.6, ease: "linear", repeat: Number.POSITIVE_INFINITY }
        }
      >
        <span className="absolute inset-x-0 top-1/2 h-px bg-petrol-500/70" />
      </motion.div>
    </div>
  );
}

function useObjectUrl(file: File): {
  url: string | null;
  containerRef: (node: HTMLElement | null) => void;
} {
  const [url, setUrl] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  const containerRef = useCallback(
    (node: HTMLElement | null) => {
      if (node) {
        if (!urlRef.current && typeof URL.createObjectURL === "function") {
          const nextUrl = URL.createObjectURL(file);
          urlRef.current = nextUrl;
          setUrl(nextUrl);
        }

        return;
      }

      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
        setUrl(null);
      }
    },
    [file],
  );

  return { url, containerRef };
}

function DocumentPreview({ file, scanning }: Readonly<{ file: File; scanning: boolean }>) {
  const { t } = useI18n();
  const { url, containerRef } = useObjectUrl(file);
  const kind = detectFileKind(file);
  const [zoom, setZoom] = useState(100);
  const canPreview = typeof URL !== "undefined" && typeof URL.createObjectURL === "function";

  function changeZoom(delta: number): void {
    setZoom((current) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current + delta)));
  }

  return (
    <section
      ref={containerRef}
      aria-label={t("verification.viewer.title")}
      className="min-w-0 rounded-[6px] border border-border bg-surface"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
            {t("verification.viewer.title")}
          </p>
          <p className="mt-1 truncate font-mono text-xs" title={file.name}>
            {file.name}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {kind === "image" ? (
            <>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("verification.dossier.document.zoomOut")}
                onClick={() => changeZoom(-ZOOM_STEP)}
                disabled={zoom <= MIN_ZOOM}
              >
                <Minus aria-hidden="true" />
              </Button>
              <span className="w-20 text-center font-mono text-[0.65rem] tabular-nums text-muted-foreground">
                {t("verification.dossier.document.zoom", { percent: zoom })}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("verification.dossier.document.zoomIn")}
                onClick={() => changeZoom(ZOOM_STEP)}
                disabled={zoom >= MAX_ZOOM}
              >
                <Plus aria-hidden="true" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("verification.dossier.document.resetZoom")}
                onClick={() => setZoom(100)}
              >
                <RotateCcw aria-hidden="true" />
              </Button>
            </>
          ) : null}
          {url ? (
            <Button asChild variant="outline" size="sm">
              <a href={url} target="_blank" rel="noreferrer">
                <ExternalLink aria-hidden="true" />
                {t("verification.dossier.document.open")}
              </a>
            </Button>
          ) : null}
        </div>
      </header>

      <div className="relative min-h-80 overflow-auto bg-surface-elevated p-3">
        {!url ? (
          <p className="p-6 text-sm text-muted-foreground">
            {canPreview ? t("verification.viewer.loading") : t("verification.viewer.unsupported")}
          </p>
        ) : kind === "pdf" ? (
          <div className="relative min-h-80">
            <iframe
              title={t("verification.dossier.document.title")}
              src={`${url}#page=1&zoom=page-width`}
              className="h-[32rem] w-full rounded-[4px] border border-border bg-background"
              referrerPolicy="no-referrer"
            />
            {scanning ? <ScanLine /> : null}
          </div>
        ) : kind === "image" ? (
          <div className="relative">
            <div className="overflow-auto">
              <Image
                src={url}
                alt={t("verification.dossier.document.imageAlt")}
                width={0}
                height={0}
                unoptimized
                sizes="(max-width: 768px) 100vw, 800px"
                className="mx-auto block h-auto max-w-none rounded-[4px] border border-border bg-background"
                style={{ width: `${zoom}%` }}
              />
            </div>
            {scanning ? <ScanLine /> : null}
          </div>
        ) : (
          <p className="p-6 text-sm text-muted-foreground">
            {t("verification.viewer.unsupported")}
          </p>
        )}
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3">
        <p className="font-mono text-[0.6rem] leading-relaxed text-muted-foreground">
          {kind === "pdf"
            ? t("verification.dossier.document.pdfHint")
            : t("verification.dossier.document.localNote")}
        </p>
        {scanning ? (
          <p className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-petrol-600">
            {t("verification.viewer.scanning")}
          </p>
        ) : null}
      </footer>
    </section>
  );
}

export function DocumentViewer({
  file,
  scanning = false,
  className,
  emptyTitle,
  emptyDescription,
}: DocumentViewerProps) {
  const { t } = useI18n();

  if (!file) {
    return (
      <div
        className={cn(
          "flex min-h-64 flex-col justify-center rounded-[6px] border border-dashed border-border bg-surface p-6",
          className,
        )}
      >
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("verification.dossier.document.title")}
        </p>
        <h2 className="mt-3 font-serif text-2xl leading-tight tracking-tight">
          {emptyTitle ?? t("verification.dossier.document.unavailableTitle")}
        </h2>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
          {emptyDescription ?? t("verification.dossier.document.unavailableDescription")}
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      <DocumentPreview
        key={`${file.name}:${file.size}:${file.lastModified}`}
        file={file}
        scanning={scanning}
      />
    </div>
  );
}
