import { z } from "zod";

import { isoDateTimeSchema, uuidSchema } from "./common";

export const documentKindSchema = z.enum(["bank_slip", "payslip", "receipt"]);

export const documentResponseSchema = z.object({
  id: uuidSchema,
  analysis_id: uuidSchema,
  kind: documentKindSchema,
  sha256: z.string(),
  size: z.number().int().nonnegative(),
  content_type: z.string(),
  original_name_sanitized: z.string(),
  created_at: isoDateTimeSchema,
});

export const documentUrlSchema = z.object({
  url: z.url(),
  expires_in: z.number().int().nonnegative(),
});

export type DocumentKind = z.infer<typeof documentKindSchema>;
export type DocumentResponse = z.infer<typeof documentResponseSchema>;
export type DocumentUrl = z.infer<typeof documentUrlSchema>;
