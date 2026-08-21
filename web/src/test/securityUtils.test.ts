import { describe, expect, it } from "vitest";
import { sanitizeMetadataRecord } from "../utils/securityUtils";

describe("sanitizeMetadataRecord", () => {
  it("redacts sensitive metadata keys and values", () => {
    const sanitized = sanitizeMetadataRecord({
      approval_token: "secret-token",
      note: "safe",
      nested: {
        authorization: "Bearer abc",
        count: 2,
      },
    });
    expect(sanitized.approval_token).toBe("[REDACTED]");
    expect(sanitized.note).toBe("safe");
    expect((sanitized.nested as Record<string, unknown>).authorization).toBe("[REDACTED]");
  });
});
