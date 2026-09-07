import { useState } from "react";
import type { SupportedLanguage } from "@/types";
import { fetchSupportedLanguages, translateDocument } from "@/api/translation";
import { renderSimplifiedText } from "@/lib/renderSimplifiedText";

type Step = "languages" | "result";

// Trigger + bottom-sheet modal for translating the current Plain Language
// result into another language, via the real, existing stateless
// /languages + /translate-document pipeline (logic/document_translation.py)
// -- the same one the static/ wizard and the QR share page already use.
// Never persisted: a fresh translation is fetched every time the picker
// opens, never written back to the document.
export default function TranslateButton({ explanationText, explainedTermsList }: {
  explanationText: string;
  explainedTermsList: string[];
}) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("languages");

  const [languages, setLanguages] = useState<SupportedLanguage[] | null>(null);
  const [loadingLanguages, setLoadingLanguages] = useState(false);
  const [languagesError, setLanguagesError] = useState<string | null>(null);

  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);
  const [result, setResult] = useState<{ languageName: string; text: string; terms: string[]; disclaimer: string } | null>(null);

  async function loadLanguages() {
    setLoadingLanguages(true);
    setLanguagesError(null);
    try {
      setLanguages(await fetchSupportedLanguages());
    } catch (err) {
      setLanguagesError(err instanceof Error ? err.message : "Could not load the language list. Please try again.");
    } finally {
      setLoadingLanguages(false);
    }
  }

  function handleOpen() {
    setOpen(true);
    setStep("languages");
    setTranslateError(null);
    setResult(null);
    if (languages === null) void loadLanguages();
  }

  async function handlePickLanguage(language: SupportedLanguage) {
    setTranslating(true);
    setTranslateError(null);
    try {
      const translation = await translateDocument(explanationText, explainedTermsList, language.code);
      setResult({
        languageName: language.name,
        text: translation.explanation_text,
        terms: translation.explained_terms_list,
        disclaimer: translation.disclaimer,
      });
      setStep("result");
    } catch (err) {
      setTranslateError(err instanceof Error ? err.message : "Could not translate this document. Please try again.");
    } finally {
      setTranslating(false);
    }
  }

  return (
    <>
      <button
        onClick={handleOpen}
        style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "10px 18px", background: "#fff", color: "#7BAAC8",
          border: "1.5px solid #D6E4EB", borderRadius: 12, cursor: "pointer",
          fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600,
          boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
        }}
      >
        <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9.5" stroke="currentColor" strokeWidth={1.8} />
          <path d="M2.5 12h19M12 2.5c2.6 2.6 4 6 4 9.5s-1.4 6.9-4 9.5c-2.6-2.6-4-6-4-9.5s1.4-6.9 4-9.5z" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Translate to another language
      </button>

      {open && (
        <div
          onClick={() => !translating && setOpen(false)}
          style={{
            position: "fixed", inset: 0, background: "rgba(44,36,32,0.45)",
            zIndex: 1000, display: "flex", alignItems: "flex-end", justifyContent: "center",
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: "#F9F7F5", borderRadius: "24px 24px 0 0",
              width: "100%", maxWidth: 480, maxHeight: "85vh",
              display: "flex", flexDirection: "column",
              boxShadow: "0 -4px 32px rgba(0,0,0,0.12)",
              animation: "slideUp 0.22s ease-out",
            }}
          >
            <style>{`
              @keyframes slideUp { from { transform: translateY(40px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
              @keyframes spin { to { transform: rotate(360deg); } }
            `}</style>

            <div style={{ padding: "12px 20px 16px", borderBottom: "1px solid #EDE9E5", flexShrink: 0 }}>
              <div style={{ width: 36, height: 4, borderRadius: 2, background: "#C4BDB9", margin: "0 auto 16px" }} />
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 17, fontWeight: 700, color: "#2C2420" }}>
                  {step === "languages" ? "Translate to another language" : `Translated to ${result?.languageName}`}
                </p>
                <button
                  onClick={() => setOpen(false)}
                  style={{ background: "#EDE9E5", border: "none", borderRadius: "50%", width: 32, height: 32, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}
                >
                  <svg width={14} height={14} viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="#6B6460" strokeWidth={2} strokeLinecap="round" /></svg>
                </button>
              </div>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "14px 20px calc(env(safe-area-inset-bottom) + 20px)" }}>
              {step === "languages" && (
                <>
                  {loadingLanguages && (
                    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "20px 0", justifyContent: "center" }}>
                      <div style={{ width: 20, height: 20, border: "2.5px solid #EDE9E5", borderTopColor: "#7BAAC8", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390" }}>Loading languages…</p>
                    </div>
                  )}
                  {languagesError && (
                    <div style={{ padding: "16px 0" }}>
                      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#E07B55", marginBottom: 10 }}>{languagesError}</p>
                      <button
                        onClick={() => void loadLanguages()}
                        style={{ padding: "8px 16px", background: "#E07B55", color: "#fff", border: "none", borderRadius: 9, fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
                      >
                        Try again
                      </button>
                    </div>
                  )}
                  {translateError && (
                    <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#E07B55", marginBottom: 10 }}>{translateError}</p>
                  )}
                  {languages && !loadingLanguages && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {languages.map(language => (
                        <button
                          key={language.code}
                          onClick={() => void handlePickLanguage(language)}
                          disabled={translating}
                          style={{
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            padding: "13px 16px", background: "#fff", border: "1.5px solid #EDE9E5",
                            borderRadius: 12, cursor: translating ? "not-allowed" : "pointer", textAlign: "left",
                            fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600, color: "#2C2420",
                          }}
                        >
                          {language.name}
                          {translating && <div style={{ width: 16, height: 16, border: "2px solid #EDE9E5", borderTopColor: "#7BAAC8", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}

              {step === "result" && result && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#2C2420", lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                    {renderSimplifiedText(result.text)}
                  </div>
                  {result.terms.length > 0 && (
                    <div>
                      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, fontWeight: 700, color: "#9B9390", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Explained terms</p>
                      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#2C2420" }}>{result.terms.join(", ")}</p>
                    </div>
                  )}
                  <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 11, color: "#C4BDB9", lineHeight: 1.5 }}>{result.disclaimer}</p>
                  <button
                    onClick={() => setStep("languages")}
                    style={{
                      alignSelf: "flex-start", padding: "9px 16px", background: "#F9F7F5", color: "#7BAAC8",
                      border: "1.5px solid #EDE9E5", borderRadius: 9, fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer",
                    }}
                  >
                    Choose another language
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
