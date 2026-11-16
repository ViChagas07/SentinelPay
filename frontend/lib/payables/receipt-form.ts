import { z } from "zod";

import { detectFileKind, getUploadMaxBytes } from "@/lib/verification/upload";

export type ReceiptFileError = "required" | "empty" | "too_large" | "unsupported_type";

const receiptFileSchema = z
  .custom<File>((value) => typeof File !== "undefined" && value instanceof File, {
    message: "required" satisfies ReceiptFileError,
  })
  .refine((file) => file.size > 0, { message: "empty" satisfies ReceiptFileError })
  .refine((file) => file.size <= getUploadMaxBytes(), {
    message: "too_large" satisfies ReceiptFileError,
  })
  .refine((file) => detectFileKind(file) !== "unknown", {
    message: "unsupported_type" satisfies ReceiptFileError,
  });

export const receiptUploadSchema = z.object({
  file: receiptFileSchema,
});

export function validateReceiptFile(file: File | null): ReceiptFileError | null {
  const result = receiptUploadSchema.safeParse({ file });

  if (result.success) {
    return null;
  }

  return (result.error.issues[0]?.message as ReceiptFileError | undefined) ?? "required";
}
