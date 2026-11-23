import type { NextRequest } from "next/server";

import { passwordAuthProxy } from "@/lib/session/password-auth";

export const dynamic = "force-dynamic";

const INVALID_BODY: Record<string, unknown> = {
  type: "about:blank",
  title: "Unprocessable entity",
  status: 422,
  detail: "Invalid request body.",
  instance: "/api/v1",
  code: "invalid_request",
  request_id: "",
};

async function proxy(request: NextRequest, path: string): Promise<Response> {
  const body: unknown = await request.json().catch(() => null);

  if (body === null || typeof body !== "object") {
    return Response.json(INVALID_BODY, {
      status: 422,
      headers: { "content-type": "application/problem+json" },
    });
  }

  const result = await passwordAuthProxy({ request, path, body });
  return result.response;
}

export async function POST(request: NextRequest) {
  return proxy(request, "/api/v1/auth/register");
}
