import { z } from "zod";

export const uuidSchema = z.uuid();
export const isoDateSchema = z.iso.date();
export const isoDateTimeSchema = z.iso.datetime({ offset: true });

export const problemSchema = z
  .object({
    type: z.string(),
    title: z.string(),
    status: z.number().int(),
    detail: z.string(),
    instance: z.string(),
    code: z.string(),
    request_id: z.string().default(""),
    evidence: z.array(z.string()).optional(),
  })
  .loose();

export function cursorPageSchema<T extends z.ZodType>(item: T) {
  return z.object({
    items: z.array(item),
    next_cursor: z.string().nullable(),
  });
}
