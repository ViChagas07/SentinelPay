import { useSyncExternalStore } from "react";

function subscribe(): () => void {
  return () => {};
}

function getSnapshot(): boolean {
  return window.isSecureContext;
}

function getServerSnapshot(): boolean {
  return false;
}

export function useSecureContext(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
