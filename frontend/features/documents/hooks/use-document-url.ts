"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch, documentUrlSchema, endpoints } from "@/lib/api";
import type { DocumentUrl } from "@/lib/api/schemas";

export function useDocumentUrl() {
  return useMutation({
    mutationFn: (documentId: string) =>
      apiFetch<DocumentUrl>(endpoints.documents.url(documentId), {
        schema: documentUrlSchema,
      }),
  });
}
