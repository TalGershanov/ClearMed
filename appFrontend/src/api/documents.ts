import { apiFetch, extractErrorMessage } from "@/api/client";
import type { ApiDocumentDetail, ApiFolder } from "@/types";

export async function fetchDocument(id: number): Promise<ApiDocumentDetail> {
  const res = await apiFetch(`/documents/${id}`);
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// The single place that calls POST /documents. user_id is never sent --
// ownership is derived server-side from the auth cookie, same as folders.
// Despite the button saying "Upload & Analyze", this only uploads/saves the
// document -- no ClearMed processing runs yet.
export async function uploadDocument(folder: ApiFolder, name: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("folder_id", String(folder.id));
  const trimmedName = name.trim();
  if (trimmedName) formData.append("name", trimmedName);
  formData.append("file", file);

  const res = await apiFetch("/documents", { method: "POST", body: formData });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
}
