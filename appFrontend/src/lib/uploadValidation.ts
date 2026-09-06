export const ACCEPTED_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png"];
export const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export function isAcceptedFile(file: File): boolean {
  if (ACCEPTED_MIME_TYPES.includes(file.type)) return true;
  // Some browsers/drag sources don't set `type` reliably -- fall back to the
  // extension as a client-side hint only. The server independently sniffs
  // real file content and is the actual source of truth for validation.
  const lower = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some(ext => lower.endsWith(ext));
}
