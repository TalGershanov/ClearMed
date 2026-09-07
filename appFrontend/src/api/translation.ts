import { apiFetch, extractErrorMessage } from "@/api/client";
import type { DocumentTranslation, SupportedLanguage } from "@/types";

// Same-origin in production (appFrontend is served from the same domain as
// the API); in local dev, covered by webapp's own CORS_ALLOWED_ORIGINS like
// every other webapp call, since server/api.py's outer CORSMiddleware wraps
// every route registered directly on `app` (these included), not just
// webapp's own routers.

// Stateless and language-list-only -- cached by the caller across opens of
// the picker, not here, so this always reflects a fresh call when invoked.
export async function fetchSupportedLanguages(): Promise<SupportedLanguage[]> {
  const res = await apiFetch("/languages");
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}

// Reuses the same stateless translation pipeline the static/ wizard and the
// QR share page use (logic/document_translation.py) -- never a second
// translation implementation. Never touches a document's persisted
// simplified_text; the caller supplies the text to translate and gets a
// translated copy back, nothing is written to the database.
export async function translateDocument(
  explanationText: string,
  explainedTermsList: string[],
  targetLanguageCode: string,
): Promise<DocumentTranslation> {
  const res = await apiFetch("/translate-document", {
    method: "POST",
    body: JSON.stringify({
      explanation_text: explanationText,
      explained_terms_list: explainedTermsList,
      target_language_code: targetLanguageCode,
    }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res));
  return res.json();
}
