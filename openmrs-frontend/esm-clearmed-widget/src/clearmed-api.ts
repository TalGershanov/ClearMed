// Thin wrapper around the *external* ClearMed FastAPI backend.
// Intentionally uses plain `fetch`, not `openmrsFetch` — `openmrsFetch`
// injects OpenMRS's own session auth/base URL and is only for calling
// OpenMRS itself, not a third-party API like this one.

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

export async function analyseText(baseUrl: string, text: string): Promise<AnalyseResponse> {
  const response = await fetch(`${baseUrl}/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(`ClearMed API error: ${response.status}`);
  }

  return response.json();
}
