import { describe, expect, it } from "vitest";

import { isEditableTarget, resolveShortcut } from "./shortcuts";

describe("shell shortcuts", () => {
  it("opens the command palette with control or meta plus k", () => {
    expect(resolveShortcut({ key: "k", ctrlKey: true, pendingG: false })).toBe("command");
    expect(resolveShortcut({ key: "K", metaKey: true, pendingG: false })).toBe("command");
  });

  it("resolves the g sequences", () => {
    expect(resolveShortcut({ key: "g", pendingG: false })).toBe("pending");
    expect(resolveShortcut({ key: "p", pendingG: true })).toBe("panel");
    expect(resolveShortcut({ key: "v", pendingG: true })).toBe("verification");
    expect(resolveShortcut({ key: "x", pendingG: true })).toBeNull();
  });

  it("resolves n and help", () => {
    expect(resolveShortcut({ key: "n", pendingG: false })).toBe("newVerification");
    expect(resolveShortcut({ key: "?", shiftKey: true, pendingG: false })).toBe("help");
  });

  it("ignores modified keys other than the command shortcut", () => {
    expect(resolveShortcut({ key: "n", ctrlKey: true, pendingG: false })).toBeNull();
    expect(resolveShortcut({ key: "g", altKey: true, pendingG: false })).toBeNull();
  });

  it("treats inputs, selects, textareas and contenteditable as editable", () => {
    const input = document.createElement("input");
    const select = document.createElement("select");
    const textarea = document.createElement("textarea");
    const editable = document.createElement("div");
    editable.setAttribute("contenteditable", "true");
    const ignored = document.createElement("div");
    ignored.dataset.shortcuts = "ignore";
    const button = document.createElement("button");

    expect(isEditableTarget(input)).toBe(true);
    expect(isEditableTarget(select)).toBe(true);
    expect(isEditableTarget(textarea)).toBe(true);
    expect(isEditableTarget(editable)).toBe(true);
    expect(isEditableTarget(ignored)).toBe(true);
    expect(isEditableTarget(button)).toBe(false);
    expect(isEditableTarget(null)).toBe(false);
  });
});
