"use client";

import { useEffect, useRef } from "react";

import { isEditableTarget, resolveShortcut } from "@/lib/shell/shortcuts";

type ShellShortcutHandlers = {
  onCommand: () => void;
  onPanel: () => void;
  onVerification: () => void;
  onNewVerification: () => void;
  onHelp: () => void;
};

const SEQUENCE_WINDOW_MS = 800;

export function useShellShortcuts(
  handlers: ShellShortcutHandlers,
  options: { enabled?: boolean } = {},
): void {
  const enabled = options.enabled ?? true;
  const handlersRef = useRef(handlers);
  const pendingUntilRef = useRef(0);

  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!enabled) {
      pendingUntilRef.current = 0;
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing || event.repeat) {
        return;
      }

      if (isEditableTarget(event.target)) {
        return;
      }

      const now = Date.now();
      const pendingG = pendingUntilRef.current > now;
      const action = resolveShortcut({
        key: event.key,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        altKey: event.altKey,
        shiftKey: event.shiftKey,
        pendingG,
      });

      if (action === null) {
        pendingUntilRef.current = 0;
        return;
      }

      if (action === "pending") {
        pendingUntilRef.current = now + SEQUENCE_WINDOW_MS;
        return;
      }

      pendingUntilRef.current = 0;
      event.preventDefault();

      if (action === "command") {
        handlersRef.current.onCommand();
      } else if (action === "panel") {
        handlersRef.current.onPanel();
      } else if (action === "verification") {
        handlersRef.current.onVerification();
      } else if (action === "newVerification") {
        handlersRef.current.onNewVerification();
      } else if (action === "help") {
        handlersRef.current.onHelp();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled]);
}
