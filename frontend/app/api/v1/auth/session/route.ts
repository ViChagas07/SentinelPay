import type { NextRequest } from "next/server";

import { refreshOnly } from "@/lib/session/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const result = await refreshOnly(request);
  return result.response;
}
