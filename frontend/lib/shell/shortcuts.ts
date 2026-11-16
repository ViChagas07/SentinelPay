export type ShellShortcutAction =
  "command" | "panel" | "verification" | "newVerification" | "help" | "pending" | null;

export type ShellShortcutInput = {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  pendingG: boolean;
};

export function resolveShortcut(input: ShellShortcutInput): ShellShortcutAction {
  const key = input.key.toLowerCase();

  if ((input.ctrlKey || input.metaKey) && !input.altKey && key === "k") {
    return "command";
  }

  if (input.ctrlKey || input.metaKey || input.altKey) {
    return null;
  }

  if (input.key === "?") {
    return "help";
  }

  if (input.pendingG) {
    if (key === "p") {
      return "panel";
    }

    if (key === "v") {
      return "verification";
    }

    return null;
  }

  if (key === "g") {
    return "pending";
  }

  if (key === "n") {
    return "newVerification";
  }

  return null;
}

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  if (target.isContentEditable) {
    return true;
  }

  if (
    target.closest(
      `[contenteditable=""], [contenteditable="true"], [contenteditable="plaintext-only"]`,
    ) !== null
  ) {
    return true;
  }

  const tag = target.tagName.toLowerCase();

  if (tag === "input" || tag === "textarea" || tag === "select") {
    return true;
  }

  return target.closest('[data-shortcuts="ignore"]') !== null;
}
