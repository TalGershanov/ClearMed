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
  // Documents directly assigned to this folder only -- never recursive into
  // child folders.
  document_count: number;
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

// Mirrors logic.medical_term_detector.detect_terms_with_explanations()'s
// output -- persisted verbatim server-side (webapp/documents/models.py's
// detected_terms JSON column), so this stays a direct mirror of that
// function's real return shape, not a separately-invented contract.
export interface DetectedTerm {
  matched_text: string;
  main_term: string; // concept_id -- the selection key, never term_name
  term_name: string;
  start: number;
  end: number;
  short_explanation: string | null;
  simple_explanation: string | null;
  categories: string[];
  synonyms: string[];
}

export type AnalysisStatus = "not_analysed" | "analysed" | "failed";
export type SimplificationStatus = "not_simplified" | "simplified" | "failed";

// Mirrors webapp/documents/schemas.py::DocumentDetail -- only ever fetched
// from GET /documents/{id} (and returned by the analyse/selection/simplify
// endpoints), never from a folder listing.
export interface ApiDocumentDetail extends ApiDocument {
  original_text: string | null;
  analysis_status: AnalysisStatus;
  // null = not analysed yet; [] = analysed, zero terms found (distinct states).
  detected_terms: DetectedTerm[] | null;
  // keyed by concept_id (DetectedTerm.main_term), never by term_name.
  term_selection: Record<string, boolean> | null;
  simplification_status: SimplificationStatus;
  simplified_text: string | null;
  // Freeform personal note the owner attaches to this document. Independent
  // of the ClearMed pipeline above.
  notes: string | null;
}

// Mirrors webapp/folders/schemas.py::FolderDetail
export interface ApiFolderDetail extends ApiFolder {
  children: ApiFolder[];
  documents: ApiDocument[];
}

// Mirrors webapp/folders/schemas.py::FolderDeletionPreview -- the real,
// recursive impact of deleting a folder with ?recursive=true. Distinct from
// ApiFolder.document_count, which is deliberately direct-only.
export interface FolderDeletionPreview {
  document_count: number;
  subfolder_count: number;
}

export type Screen = "login" | "upload" | "library" | "folder" | "document" | "terms-found";

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
