"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { buildLoginPath } from "@/lib/session/client";

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/v1/auth/logout", {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });

      return response.ok || response.status === 204;
    },
    onSettled: () => {
      queryClient.clear();
      router.replace(buildLoginPath({}));
      router.refresh();
    },
  });
}
