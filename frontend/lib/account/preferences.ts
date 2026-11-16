import { z } from "zod";

import { LOCALES } from "@/lib/i18n";
import { DATE_FORMATS } from "@/lib/preferences/date-format";
import { THEME_MODES } from "@/lib/theme/constants";

export const accountPreferencesSchema = z.object({
  locale: z.enum(LOCALES),
  theme: z.enum(THEME_MODES),
  dateFormat: z.enum(DATE_FORMATS),
});

export type AccountPreferencesValues = z.infer<typeof accountPreferencesSchema>;
