import { cookies } from "next/headers";

import { buildBackendUrl } from "@/lib/api/config";
import { userProfileSchema, type UserProfile } from "@/lib/api/schemas";

import { readSessionToken } from "./cookies";

const TIMEOUT_MS = 2_500;

export async function fetchInitialUser(): Promise<UserProfile | null> {
  const token = readSessionToken(await cookies());

  if (!token) {
    return null;
  }

  try {
    const response = await fetch(buildBackendUrl("/api/v1/users/me"), {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });

    if (!response.ok) {
      return null;
    }

    const parsed = userProfileSchema.safeParse(await response.json());
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}
