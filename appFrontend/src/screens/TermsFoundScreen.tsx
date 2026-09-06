import { useMemo, useState } from "react";
import type { DetectedTerm } from "@/types";

function BackIcon() {
  return <svg width={20} height={20} viewBox="0 0 24 24" fill="none"><path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function Spinner() {
  return <div style={{ width: 20, height: 20, border: "2.5px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />;
}

export default function TermsFoundScreen({ docName, terms, initialSelection, submitLabel = "Simplify Document", onBack, onSelectionChange, onSimplify }: {
  docName: string;
  // Real ClearMed-detected terms for this document (may be empty -- handled
  // gracefully below, never replaced with invented content).
  terms: DetectedTerm[];
  // Persisted selection, keyed by concept_id (DetectedTerm.main_term).
  initialSelection: Record<string, boolean>;
  // "Simplify Again" when reopening an already-simplified document,
  // "Simplify Document" for the first-time post-upload flow.
  submitLabel?: string;
  onBack: () => void;
  // Called (best-effort, fire-and-forget) whenever the selection changes, so
  // it survives a refresh/reopen.
  onSelectionChange: (selection: Record<string, boolean>) => void;
  // Runs the real simplification pipeline; throwing keeps the user on this
  // screen with an error shown, so they can retry without losing anything.
  onSimplify: () => Promise<void>;
}) {
  // The same concept can be detected at more than one place in the text --
  // selection is per-concept, matching the backend's own ui_selection shape,
  // so duplicate occurrences collapse to a single row here.
  const uniqueTerms = useMemo(() => {
    const seen = new Set<string>();
    const result: DetectedTerm[] = [];
    for (const t of terms) {
      if (!seen.has(t.main_term)) {
        seen.add(t.main_term);
        result.push(t);
      }
    }
    return result;
  }, [terms]);

  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(uniqueTerms.filter(t => initialSelection[t.main_term]).map(t => t.main_term)),
  );
  const [simplifying, setSimplifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function commitSelection(next: Set<string>) {
    setSelected(next);
    const selection: Record<string, boolean> = {};
    for (const t of uniqueTerms) selection[t.main_term] = next.has(t.main_term);
    onSelectionChange(selection);
  }

  function toggle(conceptId: string) {
    const next = new Set(selected);
    next.has(conceptId) ? next.delete(conceptId) : next.add(conceptId);
    commitSelection(next);
  }

  async function handleSimplify() {
    setSimplifying(true);
    setError(null);
    try {
      await onSimplify();
      // success: the app navigates away from this screen
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not simplify the document. Please try again.");
      setSimplifying(false);
    }
  }

  const count = selected.size;
  const total = uniqueTerms.length;

  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

        {/* Header */}
        <div style={{ background: "#fff", borderBottom: "1px solid #EDE9E5", paddingTop: "calc(env(safe-area-inset-top) + 52px)", paddingBottom: 18, paddingLeft: 16, paddingRight: 16, flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: "#7BAAC8", display: "flex", padding: 4, flexShrink: 0 }}>
              <BackIcon />
            </button>
            <div>
              <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 18, fontWeight: 700, color: "#2C2420" }}>Terms Found</p>
              <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 260 }}>{docName}</p>
            </div>
          </div>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px 0" }}>

          {/* Intro */}
          <div style={{ background: "rgba(123,170,200,0.10)", borderRadius: 14, padding: "14px 16px", marginBottom: 20 }}>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, color: "#2C2420", lineHeight: 1.6, marginBottom: 6 }}>
              We found medical terms in your document.<br />Choose which ones you'd like us to explain.
            </p>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, fontWeight: 600, color: "#7BAAC8" }}>
              {total === 0 ? "No terms found" : `${total} term${total !== 1 ? "s" : ""} found`}
            </p>
          </div>

          {total > 0 && (
            <>
              {/* Select all / Clear all */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginBottom: 12 }}>
                <button onClick={() => commitSelection(new Set(uniqueTerms.map(t => t.main_term)))} style={{ background: "none", border: "none", fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, color: "#7BAAC8", cursor: "pointer", padding: 0 }}>Select all</button>
                <button onClick={() => commitSelection(new Set())} style={{ background: "none", border: "none", fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, color: "#C4BDB9", cursor: "pointer", padding: 0 }}>Clear all</button>
              </div>

              {/* Term cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingBottom: 24 }}>
                {uniqueTerms.map(t => {
                  const isSelected = selected.has(t.main_term);
                  return (
                    <button
                      key={t.main_term}
                      onClick={() => toggle(t.main_term)}
                      style={{
                        display: "flex", alignItems: "flex-start", gap: 14, padding: "14px 16px",
                        background: "#fff", border: `1.5px solid ${isSelected ? "#7BAAC8" : "#EDE9E5"}`,
                        borderRadius: 16, cursor: "pointer", textAlign: "left", width: "100%",
                        boxShadow: isSelected ? "0 0 0 3px rgba(123,170,200,0.12)" : "0 1px 3px rgba(0,0,0,0.05)",
                        transition: "all 0.15s",
                      }}
                    >
                      <div style={{
                        width: 22, height: 22, borderRadius: 6, flexShrink: 0, marginTop: 2,
                        background: isSelected ? "#7BAAC8" : "#fff",
                        border: `2px solid ${isSelected ? "#7BAAC8" : "#C4BDB9"}`,
                        display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.15s",
                      }}>
                        {isSelected && <svg width={12} height={12} viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></svg>}
                      </div>
                      <div style={{ flex: 1 }}>
                        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 15, fontWeight: 700, color: "#2C2420", marginBottom: 4 }}>{t.term_name}</p>
                        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390", lineHeight: 1.55 }}>
                          {t.short_explanation || "No explanation available for this term."}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {total === 0 && (
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#C4BDB9", textAlign: "center", padding: "32px 0" }}>
              No medical terms were detected in this document. You can still continue -- the plain-language result will match the original text.
            </p>
          )}
        </div>

        {/* Bottom bar */}
        <div style={{ background: "#fff", borderTop: "1px solid #EDE9E5", padding: "14px 16px calc(env(safe-area-inset-bottom) + 14px)", flexShrink: 0 }}>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390", textAlign: "center", marginBottom: 12 }}>
            <span style={{ fontWeight: 700, color: "#2C2420" }}>{count}</span> of {total} terms selected
          </p>
          {error && <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#E07B55", textAlign: "center", marginBottom: 10 }}>{error}</p>}
          <button
            onClick={handleSimplify}
            disabled={simplifying}
            style={{
              width: "100%", padding: "16px", border: "none", borderRadius: 14,
              background: simplifying ? "#F0A888" : "#E07B55",
              color: "#fff",
              fontFamily: "Outfit, sans-serif", fontSize: 17, fontWeight: 600,
              cursor: simplifying ? "not-allowed" : "pointer", transition: "background 0.2s",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            }}
          >
            {simplifying ? <><Spinner />Simplifying…</> : submitLabel}
          </button>
        </div>

      </div>
    </>
  );
}
