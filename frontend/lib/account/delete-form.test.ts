import { describe, expect, it } from "vitest";

import { buildDeleteAccountSchema } from "./delete-form";

describe("delete account confirmation", () => {
  it("accepts the exact confirmation word", () => {
    const schema = buildDeleteAccountSchema("EXCLUIR");

    expect(schema.safeParse({ confirmation: "EXCLUIR" }).success).toBe(true);
    expect(schema.safeParse({ confirmation: " EXCLUIR " }).success).toBe(true);
  });

  it("rejects another word and an empty value", () => {
    const schema = buildDeleteAccountSchema("EXCLUIR");
    const wrong = schema.safeParse({ confirmation: "APAGAR" });
    const empty = schema.safeParse({ confirmation: "" });

    expect(wrong.success).toBe(false);
    expect(empty.success).toBe(false);

    if (!wrong.success) {
      expect(wrong.error.issues[0]?.message).toBe("word");
    }
  });

  it("uses the translated word", () => {
    const schema = buildDeleteAccountSchema("DELETE");

    expect(schema.safeParse({ confirmation: "DELETE" }).success).toBe(true);
    expect(schema.safeParse({ confirmation: "EXCLUIR" }).success).toBe(false);
  });
});
