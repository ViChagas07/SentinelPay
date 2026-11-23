import type { NextRequest } from "next/server";

import { passwordAuthProxy } from "@/lib/session/password-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body: unknown = await request.json().catch(() => null);

  if (body === null || typeof body !== "object") {
    return Response.json(
      {
        type: "about:blank",
        title: "Unprocessable entity",
        status: 422,
        detail: "Invalid request body.",
        instance: "/api/v1",
        code: "invalid_request",
        request_id: "",
      },
      { status: 422, headers: { "content-type": "application/problem+json" } },
    );
  }

  const result = await passwordAuthProxy({
    request,
    path: "/api/v1/auth/reset-password",
    body,
  });

  return result.response;
}
