import type { NextRequest } from "next/server";

import { isAbortError } from "@/lib/session/backend";
import { sessionRequest } from "@/lib/session/server";

export const dynamic = "force-dynamic";

const FORWARD_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);

async function handler(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const method = request.method.toUpperCase();

  if (!FORWARD_METHODS.has(method)) {
    return new Response(null, {
      status: 405,
      headers: { Allow: [...FORWARD_METHODS].join(", ") },
    });
  }

  const segments = path ?? [];

  if (segments.length === 0) {
    return Response.json(
      {
        type: "about:blank",
        title: "Not found",
        status: 404,
        detail: "Missing API path.",
        instance: "/api/v1",
        code: "not_found",
        request_id: "",
      },
      { status: 404, headers: { "content-type": "application/problem+json" } },
    );
  }

  const search = request.nextUrl.search;
  const backendPath = `/api/v1/${segments.join("/")}${search}`;
  const hasBody = method !== "GET" && method !== "HEAD";
  const body = hasBody ? await request.arrayBuffer() : undefined;

  try {
    const result = await sessionRequest({
      request,
      path: backendPath,
      method,
      body,
      signal: request.signal,
    });

    return result.response;
  } catch (error) {
    if (isAbortError(error)) {
      return new Response(null, { status: 499 });
    }

    if (error instanceof Error && error.name === "TimeoutError") {
      return Response.json(
        {
          type: "about:blank",
          title: "Gateway timeout",
          status: 504,
          detail: "The API did not respond in time.",
          instance: "/api/v1",
          code: "request_timeout",
          request_id: "",
        },
        { status: 504, headers: { "content-type": "application/problem+json" } },
      );
    }

    throw error;
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
