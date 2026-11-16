import { z } from "zod";

import { uuidSchema } from "./common";

export const userRoleSchema = z.enum(["user", "admin"]);

export const authUserSchema = z.object({
  id: uuidSchema,
  email: z.email(),
  name: z.string().nullable(),
  role: userRoleSchema,
  preferred_locale: z.string(),
  timezone: z.string(),
});

export const refreshResponseSchema = z.object({
  access_token: z.string().min(1),
  token_type: z.literal("bearer"),
  expires_in: z.number().int().nonnegative(),
  user: authUserSchema,
});

export type AuthUser = z.infer<typeof authUserSchema>;
export type RefreshResponse = z.infer<typeof refreshResponseSchema>;
