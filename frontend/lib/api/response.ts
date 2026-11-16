import type { ZodType } from "zod";

import { ApiError, readApiError } from "./errors";

export async function handleResponse<T>(response: Response, schema?: ZodType<T>): Promise<T> {
  const requestId = response.headers.get("x-request-id");

  if (!response.ok) {
    throw await readApiError(response);
  }

  if (response.status === 204) {
    if (schema) {
      throw new ApiError({
        status: response.status,
        code: "response_schema_invalid",
        title: "Invalid response",
        detail: "The API returned no body where a body was expected.",
        requestId,
      });
    }

    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;

  if (text.length > 0) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new ApiError({
        status: response.status,
        code: "invalid_response",
        title: "Invalid response",
        detail: "The API response is not valid JSON.",
        requestId,
        cause: error,
      });
    }
  }

  if (!schema) {
    return undefined as T;
  }

  const parsed = schema.safeParse(payload);

  if (!parsed.success) {
    throw new ApiError({
      status: response.status,
      code: "response_schema_invalid",
      title: "Invalid response",
      detail: "The API response did not match the expected schema.",
      requestId,
      issues: parsed.error.issues,
    });
  }

  return parsed.data;
}
