import { apiFetch, extractErrorMessage } from "@/api/client";
import type { ApiDocument, ApiDocumentDetail, ApiFolder } from "@/types";

export async function fetchDocument(id: number): Promise<ApiDocumentDetail> {
  const res = await apiFetch(`/documents/${id}`);
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// The single place that calls POST /documents. user_id is never sent --
// ownership is derived server-side from the auth cookie, same as folders.
export async function uploadDocument(folder: ApiFolder, name: string, file: File): Promise<ApiDocument> {
  const formData = new FormData();
  formData.append("folder_id", String(folder.id));
  const trimmedName = name.trim();
  if (trimmedName) formData.append("name", trimmedName);
  formData.append("file", file);

  const res = await apiFetch("/documents", { method: "POST", body: formData });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Runs the same ClearMed term-detection logic /analyse uses, against this
// document's own extracted text. Idempotent server-side -- safe to call
// again for an already-analysed document (returns the persisted result).
export async function analyseDocument(id: number): Promise<ApiDocumentDetail> {
  const res = await apiFetch(`/documents/${id}/analyse`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Persists the user's current term selection, keyed by concept_id, so it
// survives a refresh/reopen.
export async function updateTermSelection(
  id: number,
  termSelection: Record<string, boolean>,
): Promise<ApiDocumentDetail> {
  const res = await apiFetch(`/documents/${id}/selection`, {
    method: "PATCH",
    body: JSON.stringify({ term_selection: termSelection }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Runs the same ClearMed translation pipeline /translate uses, against this
// document's persisted analysis + selection. Freely re-callable (retry).
export async function simplifyDocument(id: number): Promise<ApiDocumentDetail> {
  const res = await apiFetch(`/documents/${id}/simplify`, { method: "POST" });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Persists the user's personal note on this document. Independent of the
// ClearMed pipeline -- callable regardless of analysis/simplification state.
export async function updateDocumentNotes(id: number, notes: string): Promise<ApiDocumentDetail> {
  const res = await apiFetch(`/documents/${id}/notes`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Unconditional (no "has children" concept for a document) -- deletes the DB
// row and the stored file. 204 No Content on success.
export async function deleteDocument(id: number): Promise<void> {
  const res = await apiFetch(`/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
}
