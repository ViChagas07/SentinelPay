export const BACK_FALLBACK_PATH = "/";

export type BackNavigationAction = "history" | "fallback";

export function resolveBackNavigationAction(historyLength: number): BackNavigationAction {
  return historyLength > 1 ? "history" : "fallback";
}
