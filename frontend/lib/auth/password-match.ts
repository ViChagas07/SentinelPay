import { useEffect, useMemo, useState } from "react";

export const PASSWORD_MATCH_DEBOUNCE_MS = 350;

export type PasswordMatchState = "idle" | "waiting" | "match" | "mismatch";

export function evaluatePasswordMatch(password: string, confirmation: string): PasswordMatchState {
  if (password.length === 0 && confirmation.length === 0) {
    return "idle";
  }

  if (confirmation.length === 0) {
    return "idle";
  }

  return password === confirmation ? "match" : "mismatch";
}

export function useDebouncedPasswordMatch(
  password: string,
  confirmation: string,
  delayMs: number = PASSWORD_MATCH_DEBOUNCE_MS,
): PasswordMatchState {
  const immediate = useMemo(
    () => evaluatePasswordMatch(password, confirmation),
    [password, confirmation],
  );
  const [settled, setSettled] = useState<PasswordMatchState>(immediate);

  useEffect(() => {
    if (immediate === "match" || immediate === "idle") {
      return;
    }

    const timer = window.setTimeout(() => {
      setSettled(evaluatePasswordMatch(password, confirmation));
    }, delayMs);

    return () => window.clearTimeout(timer);
  }, [immediate, password, confirmation, delayMs]);

  if (immediate === "match" || immediate === "idle") {
    return immediate;
  }

  return settled;
}
