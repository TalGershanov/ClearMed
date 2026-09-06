// Thin wrapper around the *external* ClearMed FastAPI backend.
// Intentionally uses plain `fetch`, not `openmrsFetch` — `openmrsFetch`
// injects OpenMRS's own session auth/base URL and is only for calling
// OpenMRS itself, not a third-party API like this one.
//
// analyseText/translateText call ClearMed's /openmrs/analyse and
// /openmrs/translate — mirrors of the top-level /analyse and /translate
// used by the static wizard, registered on ClearMed's CORS-scoped OpenMRS
// sub-app so a browser running on the OpenMRS origin is actually allowed to
// call them (the top-level /analyse and /translate have no CORS headers at
// all, since they're only meant for same-origin use by the static wizard).
// fetchPatientNotes calls a genuinely OpenMRS-specific endpoint under the
// same sub-app.

export interface DetectedTerm {
  matched_text: string;
  main_term: string;
  start_word_index: number;
  end_word_index: number;
  short_explanation: string;
  simple_explanation: string;
  categories: string[];
  synonyms: string[];
}

export interface AnalyseResponse {
  detected_terms: DetectedTerm[];
  ui_selection: Record<string, boolean>;
}

export interface TranslateResponse {
  translated_text: string;
  explained_terms_list: string[];
}

export interface PatientNote {
  obs_uuid: string;
  obs_datetime: string | null;
  note_text: string;
}

export interface CreateShareResponse {
  uuid: string;
}

async function toError(response: Response): Promise<Error> {
  try {
    const body: { detail?: string } = await response.json();
    if (body.detail) {
      return new Error(body.detail);
    }
  } catch {
    // response body wasn't JSON (or had no `detail`) -- fall through
  }
  return new Error(`ClearMed API error: ${response.status}`);
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await toError(response);
  }
  return response.json();
}

export async function analyseText(baseUrl: string, text: string): Promise<AnalyseResponse> {
  return postJson(`${baseUrl}/openmrs/analyse`, { text });
}

export async function translateText(
  baseUrl: string,
  text: string,
  uiSelection: Record<string, boolean>,
): Promise<TranslateResponse> {
  return postJson(`${baseUrl}/openmrs/translate`, { text, ui_selection: uiSelection });
}

export async function createDocumentShare(
  baseUrl: string,
  explanationText: string,
  explainedTermsList: string[],
): Promise<CreateShareResponse> {
  return postJson(`${baseUrl}/openmrs/documents/share`, {
    explanation_text: explanationText,
    explained_terms_list: explainedTermsList,
  });
}

export async function fetchPatientNotes(baseUrl: string, patientUuid: string): Promise<PatientNote[]> {
  const response = await fetch(`${baseUrl}/openmrs/patients/${patientUuid}/notes`);
  if (!response.ok) {
    throw await toError(response);
  }
  const data: { notes: PatientNote[] } = await response.json();
  return data.notes;
}
