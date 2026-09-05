export interface ApiUser {
  id: number;
  email: string;
  created_at: string;
}

// Mirrors webapp/folders/schemas.py::FolderOut
export interface ApiFolder {
  id: number;
  name: string;
  parent_folder_id: number | null;
  color: string | null;
  cover_image_path: string | null;
  created_at: string;
  updated_at: string;
}

// Mirrors webapp/documents/schemas.py::DocumentOut -- used in folder
// listings. Deliberately no original_text (see ApiDocumentDetail below).
export interface ApiDocument {
  id: number;
  folder_id: number;
  name: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  extraction_status: "pending" | "extracted" | "no_text_found" | "failed";
  created_at: string;
  updated_at: string;
}

// Mirrors webapp/documents/schemas.py::DocumentDetail -- only ever fetched
// from GET /documents/{id}, never from a folder listing.
export interface ApiDocumentDetail extends ApiDocument {
  original_text: string | null;
}

// Mirrors webapp/folders/schemas.py::FolderDetail
export interface ApiFolderDetail extends ApiFolder {
  children: ApiFolder[];
  documents: ApiDocument[];
}

export type Screen = "login" | "upload" | "library" | "folder" | "document";

// Mock documents, used only by the Library search box -- no backend
// document search exists yet (out of scope for now).
export interface Doc {
  id: string;
  name: string;
  folder: string;
  date: string;
  type: string;
  translated?: boolean;
}

export interface FolderStyle {
  bg: string;
  color: string;
  image?: string;
}
