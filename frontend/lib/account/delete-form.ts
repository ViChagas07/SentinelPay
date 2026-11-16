import { z } from "zod";

export function buildDeleteAccountSchema(confirmationWord: string) {
  return z.object({
    confirmation: z.string().refine((value) => value.trim() === confirmationWord, {
      message: "word",
    }),
  });
}

export type DeleteAccountValues = z.infer<ReturnType<typeof buildDeleteAccountSchema>>;
