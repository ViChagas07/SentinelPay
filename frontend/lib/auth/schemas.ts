import { z } from "zod";

const EMAIL_PATTERN =
  /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export const emailSchema = z
  .string()
  .trim()
  .min(1)
  .max(320)
  .regex(EMAIL_PATTERN)
  .transform((value) => value.toLowerCase());

export const passwordLoginSchema = z.strictObject({
  email: emailSchema,
  senha: z.string().min(1).max(256),
});

export type PasswordLoginInput = z.infer<typeof passwordLoginSchema>;

export const registerSchema = z.strictObject({
  nome_completo: z.string().trim().min(1).max(255),
  email: emailSchema,
  senha: z.string().min(1).max(256),
  aceite_termos: z.literal(true),
  aceite_privacidade: z.literal(true),
});

export type RegisterInput = z.infer<typeof registerSchema>;

export const verifyEmailSchema = z.strictObject({
  token: z.string().min(10).max(512),
});

export const emailRequestSchema = z.strictObject({
  email: emailSchema,
});

export const resetPasswordSchema = z.strictObject({
  token: z.string().min(10).max(512),
  nova_senha: z.string().min(1).max(256),
});

export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
