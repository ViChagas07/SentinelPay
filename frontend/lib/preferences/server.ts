import { cookies } from "next/headers";

import { DATE_FORMAT_COOKIE, resolveDateFormat, type DateFormat } from "./date-format";

export async function getServerDateFormat(): Promise<DateFormat> {
  const cookieStore = await cookies();
  return resolveDateFormat(cookieStore.get(DATE_FORMAT_COOKIE)?.value);
}
