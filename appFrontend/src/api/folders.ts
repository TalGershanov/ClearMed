import { apiFetch, extractErrorMessage } from "@/api/client";
import type { ApiFolder, ApiFolderDetail, FolderDeletionPreview } from "@/types";

export async function fetchRootFolders(): Promise<ApiFolder[]> {
  const res = await apiFetch("/folders");
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

export async function fetchFolder(id: number): Promise<ApiFolderDetail> {
  const res = await apiFetch(`/folders/${id}`);
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// The single place that calls POST /folders. user_id is never sent --
// ownership is derived server-side from the auth cookie.
export async function createFolder(name: string, color: string, parentFolderId: number | null): Promise<void> {
  const res = await apiFetch("/folders", {
    method: "POST",
    body: JSON.stringify({ name, color, parent_folder_id: parentFolderId }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
}

// The real, recursive count of everything inside this folder -- fetched so
// the delete confirmation can show an accurate warning before the user
// commits to a cascading delete, never a client-side guess.
export async function fetchFolderDeletionPreview(id: number): Promise<FolderDeletionPreview> {
  const res = await apiFetch(`/folders/${id}/deletion-preview`);
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// By default the backend refuses (409, with a specific detail message) to
// delete a folder that still has child folders or documents -- that error
// message is surfaced to the user as-is via extractErrorMessage.
// recursive=true is an explicit opt-in (only ever sent after the user has
// confirmed the real impact from fetchFolderDeletionPreview above) that
// permanently deletes the folder, every descendant folder, and every
// document (including its stored file) inside them.
export async function deleteFolder(id: number, recursive = false): Promise<void> {
  const res = await apiFetch(`/folders/${id}${recursive ? "?recursive=true" : ""}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
}
