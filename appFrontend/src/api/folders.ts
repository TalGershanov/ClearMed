import { apiFetch, extractErrorMessage } from "@/api/client";
import type { ApiFolder, ApiFolderDetail } from "@/types";

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
