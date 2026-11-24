import {
  fetchPublicJson,
  publicJsonResponse,
  PUBLIC_CAPABILITIES_PATH,
} from "@/lib/auth/public-capabilities";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const payload = await fetchPublicJson(PUBLIC_CAPABILITIES_PATH);

  return publicJsonResponse(payload ?? {}, 200);
}
