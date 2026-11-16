import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useUnsavedChangesWarning } from "./use-unsaved-changes-warning";

describe("useUnsavedChangesWarning", () => {
  it("prevents unload while enabled and releases after cleanup", () => {
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useUnsavedChangesWarning(enabled),
      { initialProps: { enabled: true } },
    );
    const blocked = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(blocked);
    expect(blocked.defaultPrevented).toBe(true);

    rerender({ enabled: false });
    const released = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(released);
    expect(released.defaultPrevented).toBe(false);
  });
});
