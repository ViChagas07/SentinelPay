import { z } from "zod";

import { cursorPageSchema, isoDateTimeSchema, uuidSchema } from "./common";

export const analysisKindSchema = z.enum(["boleto", "payslip", "receipt"]);

export const analysisStatusSchema = z.enum([
  "queued",
  "running",
  "processing",
  "cancelling",
  "cancelled",
  "completed",
  "degraded",
  "failed",
]);

export const analysisStageSchema = z.enum([
  "validation",
  "ocr",
  "extraction",
  "classification",
  "rag",
  "llm",
  "persistence",
]);

export const analysisProgressSchema = z.object({
  percent: z.number().int().min(0).max(100),
  stage: analysisStageSchema.nullable(),
  detail: z.string().nullable(),
  started_at: isoDateTimeSchema.nullable(),
  indeterminate: z.boolean(),
});

export const riskBandSchema = z.enum(["low", "attention", "high"]);

export const evidenceSeveritySchema = z.enum(["critical", "high", "medium", "low", "info"]);

export const analysisEvidenceSchema = z.object({
  rule_id: z.string(),
  severity: evidenceSeveritySchema,
  weight: z.number(),
  message_key: z.string(),
  source: z.string(),
});

export const analysisResultSchema = z.object({
  score: z.number().int().min(0).max(100),
  band: riskBandSchema,
  base_score: z.number().int().min(0).max(100),
  llm_adjustment: z.number().int().min(0).max(20),
  evidence: z.array(analysisEvidenceSchema),
  justification: z.string(),
  inconsistencies: z.array(z.string()),
  degradation_flags: z.array(z.string()),
});

export const analysisDetailSchema = z.object({
  id: uuidSchema,
  status: analysisStatusSchema,
  kind: analysisKindSchema,
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
  error_code: z.string().nullable(),
  result_available: z.boolean(),
  result: analysisResultSchema.nullable(),
  progress: analysisProgressSchema.nullable().optional(),
  cancelled_at: isoDateTimeSchema.nullable().optional(),
});

export const analysisProgressEventSchema = z.object({
  id: uuidSchema,
  status: analysisStatusSchema,
  kind: analysisKindSchema,
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
  error_code: z.string().nullable(),
  result_available: z.boolean(),
  progress: analysisProgressSchema,
  cancelled_at: isoDateTimeSchema.nullable(),
});

export const analysisListItemSchema = z.object({
  id: uuidSchema,
  status: analysisStatusSchema,
  kind: analysisKindSchema,
  score: z.number().int().min(0).max(100).nullable(),
  band: riskBandSchema.nullable(),
  error_code: z.string().nullable(),
  created_at: isoDateTimeSchema,
  updated_at: isoDateTimeSchema,
});

export const analysisListSchema = cursorPageSchema(analysisListItemSchema);

export const createAnalysisResponseSchema = z.object({
  analysis_id: uuidSchema,
  status: analysisStatusSchema,
});

export const cancelAnalysisResponseSchema = z.object({
  analysis_id: uuidSchema,
  status: analysisStatusSchema,
});

export type AnalysisKind = z.infer<typeof analysisKindSchema>;
export type AnalysisStatus = z.infer<typeof analysisStatusSchema>;
export type AnalysisStage = z.infer<typeof analysisStageSchema>;
export type AnalysisProgress = z.infer<typeof analysisProgressSchema>;
export type AnalysisProgressEvent = z.infer<typeof analysisProgressEventSchema>;
export type RiskBand = z.infer<typeof riskBandSchema>;
export type EvidenceSeverity = z.infer<typeof evidenceSeveritySchema>;
export type AnalysisEvidence = z.infer<typeof analysisEvidenceSchema>;
export type AnalysisResult = z.infer<typeof analysisResultSchema>;
export type AnalysisDetail = z.infer<typeof analysisDetailSchema>;
export type AnalysisListItem = z.infer<typeof analysisListItemSchema>;
export type AnalysisList = z.infer<typeof analysisListSchema>;
export type CreateAnalysisResponse = z.infer<typeof createAnalysisResponseSchema>;
export type CancelAnalysisResponse = z.infer<typeof cancelAnalysisResponseSchema>;
