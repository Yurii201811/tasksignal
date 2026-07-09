export function apiErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) return "The request failed.";
  try {
    const parsed = JSON.parse(error.message) as {
      detail?: string | { msg?: string }[] | unknown;
    };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      const messages = parsed.detail
        .map((entry) => (typeof entry?.msg === "string" ? entry.msg : ""))
        .filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
    if (parsed.detail !== undefined) return JSON.stringify(parsed.detail);
  } catch {
    return error.message;
  }
  return error.message;
}
