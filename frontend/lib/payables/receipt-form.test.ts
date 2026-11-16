import { describe, expect, it } from "vitest";

import { receiptUploadSchema, validateReceiptFile } from "./receipt-form";

describe("receiptUploadSchema", () => {
  it("requires a file", () => {
    const result = receiptUploadSchema.safeParse({ file: null });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("required");
    }
  });

  it("rejects empty and unsupported files", () => {
    const empty = new File([], "recibo.pdf", { type: "application/pdf" });
    const unsupported = new File(["conteudo"], "recibo.txt", { type: "text/plain" });

    expect(validateReceiptFile(empty)).toBe("empty");
    expect(validateReceiptFile(unsupported)).toBe("unsupported_type");
  });

  it("accepts a PDF", () => {
    const file = new File(["%PDF-1.4"], "recibo.pdf", { type: "application/pdf" });

    expect(validateReceiptFile(file)).toBeNull();
  });
});
