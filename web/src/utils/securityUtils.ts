const SENSITIVE_KEY_PATTERN =
  /token|authorization|credential|api[_-]?key|secret|password|webhook|bearer|private[_-]?key/i;

export function looksLikeSecret(value: string): boolean {
  const lowered = value.toLowerCase();
  return (
    lowered.includes("bearer ") ||
    lowered.includes("authorization") ||
    lowered.includes("api_key") ||
    lowered.includes("credential") ||
    lowered.includes("webhook") ||
    value.length > 120
  );
}

export function isSensitiveKey(key: string): boolean {
  return SENSITIVE_KEY_PATTERN.test(key);
}

export function sanitizeMetadataValue(value: unknown): unknown {
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof value === "string") {
    return looksLikeSecret(value) ? "[REDACTED]" : value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeMetadataValue(item));
  }
  if (typeof value === "object") {
    return sanitizeMetadataRecord(value as Record<string, unknown>);
  }
  return value;
}

export function sanitizeMetadataRecord(
  record: Record<string, unknown>,
): Record<string, unknown> {
  const sanitized: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(record)) {
    if (isSensitiveKey(key)) {
      sanitized[key] = "[REDACTED]";
      continue;
    }
    sanitized[key] = sanitizeMetadataValue(value);
  }
  return sanitized;
}
