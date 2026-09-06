import React, { useState } from "react";
import { createPortal } from "react-dom";
import { useConfig } from "@openmrs/esm-framework";
import {
  analyseText,
  translateText,
  type AnalyseResponse,
  type TranslateResponse,
} from "./clearmed-api";
import type { ConfigSchema } from "./config-schema";
import logo from "./assets/logo-symbol.png";
import logoFull from "./assets/logo.png";
import styles from "./clearmed-widget.scss";

interface ClearmedWidgetProps {
  patientUuid: string;
}

type Step = "writing-notes" | "reviewing-terms" | "reviewing-translation" | "result";

function combineNoteText(visitNotes: string, recommendation: string): string {
  return `Visit notes:\n${visitNotes}\n\nRecommendation & medication:\n${recommendation}`;
}

export default function ClearmedWidget({ patientUuid }: ClearmedWidgetProps) {
  const config = useConfig<ConfigSchema>();
  const { clearmedApiBaseUrl } = config;

  const [step, setStep] = useState<Step>("writing-notes");

  const [visitNotes, setVisitNotes] = useState("");
  const [recommendation, setRecommendation] = useState("");

  const [analysing, setAnalysing] = useState(false);
  const [analyseResult, setAnalyseResult] = useState<AnalyseResponse | null>(null);
  const [analyseError, setAnalyseError] = useState<string | null>(null);

  const [uiSelection, setUiSelection] = useState<Record<string, boolean>>({});
  const [translateResult, setTranslateResult] = useState<TranslateResponse | null>(null);
  const [translateError, setTranslateError] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
  const [editedText, setEditedText] = useState("");
  const [editingManually, setEditingManually] = useState(false);

  const canSubmit = visitNotes.trim().length > 0 || recommendation.trim().length > 0;

  const submitNotes = async () => {
    setAnalysing(true);
    setAnalyseError(null);
    try {
      const result = await analyseText(clearmedApiBaseUrl, combineNoteText(visitNotes, recommendation));
      setAnalyseResult(result);
      setUiSelection(result.ui_selection);
      setStep("reviewing-terms");
    } catch (e) {
      setAnalyseError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setAnalysing(false);
    }
  };

  const toggleTerm = (term: string) => {
    setUiSelection((prev) => ({ ...prev, [term]: !prev[term] }));
  };

  const generate = async () => {
    setTranslating(true);
    setTranslateError(null);
    try {
      const result = await translateText(
        clearmedApiBaseUrl,
        combineNoteText(visitNotes, recommendation),
        uiSelection,
      );
      setTranslateResult(result);
      setEditedText(result.translated_text);
      setStep("reviewing-translation");
    } catch (e) {
      setTranslateError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setTranslating(false);
    }
  };

  // Returns to writing-notes without losing what was typed -- only the
  // stale analysis/translation results are cleared, since they no longer
  // match the text once it's edited and resubmitted.
  const goBack = () => {
    setStep("writing-notes");
    setAnalyseResult(null);
    setAnalyseError(null);
    setUiSelection({});
    setTranslateResult(null);
    setTranslateError(null);
    setEditedText("");
    setEditingManually(false);
  };

  // Returns to term selection from the review-translation step -- clears
  // the now-stale translation so regenerating reflects any changed term
  // selection, but keeps the detected terms and notes so the user doesn't
  // have to re-submit them.
  const backToTerms = () => {
    setStep("reviewing-terms");
    setTranslateResult(null);
    setTranslateError(null);
    setEditedText("");
    setEditingManually(false);
  };

  const approveTranslation = () => {
    setEditingManually(false);
    setStep("result");
  };

  // Full reset -- matches static/script.js's btn-new-doc handler. Only
  // reachable from the result screen's "Start New Document" button.
  const startOver = () => {
    setStep("writing-notes");
    setVisitNotes("");
    setRecommendation("");
    setAnalyseResult(null);
    setAnalyseError(null);
    setUiSelection({});
    setTranslateResult(null);
    setTranslateError(null);
    setEditedText("");
    setEditingManually(false);
  };

  const printDoc = () => {
    window.print();
  };

  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // Shared between the on-screen document and its print-only portal copy
  // (see the "result" step below) so the two can't drift out of sync.
  const renderDocContent = () => {
    if (!translateResult) return null;
    return (
      <>
        <div className={styles.docHeader}>
          <img src={logoFull} alt="ClearMed" className={styles.docLogo} />
          <span className={styles.docDate}>{today}</span>
        </div>
        <h3 className={styles.docTitle}>Patient-Friendly Summary</h3>

        <div className={styles.docExplanation}>
          <p dir="auto">{editedText}</p>
        </div>

        <div className={styles.docTerms}>
          <h4>Selected Terms</h4>
          <ul>
            {translateResult.explained_terms_list.map((term) => (
              <li key={term}>{term}</li>
            ))}
          </ul>
        </div>

        <p className={styles.docDisclaimer}>
          Term explanations are sourced from MedlinePlus, a service of the U.S. National Library of
          Medicine (NIH), and were shortened and summarized with the help of AI for readability. This
          document is not a substitute for professional medical advice.
        </p>
      </>
    );
  };

  return (
    <div className={styles.widget}>
      <div className={styles.header}>
        <img src={logo} alt="" className={styles.headerLogo} />
        <h3 className={styles.headerTitle}>ClearMed</h3>
      </div>

      {step === "writing-notes" && (
        <section>
          <div className={styles.card}>
            <div className={styles.cardTitle}>Visit Notes</div>
            <div className={styles.cardAccent} />
            <textarea
              className={styles.textarea}
              value={visitNotes}
              onChange={(e) => setVisitNotes(e.target.value)}
              placeholder="Type visit notes here…"
            />
          </div>

          <div className={styles.card}>
            <div className={styles.cardTitle}>Recommendation &amp; Medication</div>
            <div className={styles.cardAccent} />
            <textarea
              className={styles.textarea}
              value={recommendation}
              onChange={(e) => setRecommendation(e.target.value)}
              placeholder="Type recommendation &amp; medication here…"
            />
          </div>

          {analyseError && <p className={styles.error} role="alert">{analyseError}</p>}

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={submitNotes}
              disabled={!canSubmit || analysing}
            >
              {analysing ? "Analyzing…" : "Continue"}
            </button>
          </div>
        </section>
      )}

      {step === "reviewing-terms" && analyseResult && (
        <section>
          <div className={styles.card}>
            <div className={styles.cardTitle}>Select terms to explain</div>
            <div className={styles.cardAccent} />
            {analyseResult.detected_terms.length === 0 && (
              <p className={styles.muted}>No terms detected in this note.</p>
            )}
            <ul className={styles.termList}>
              {analyseResult.detected_terms.map((term) => (
                <li key={term.main_term}>
                  <label className={styles.termLabel}>
                    <input
                      type="checkbox"
                      checked={!!uiSelection[term.main_term]}
                      onChange={() => toggleTerm(term.main_term)}
                    />
                    {term.matched_text}
                  </label>
                </li>
              ))}
            </ul>
          </div>

          {translateError && <p className={styles.error} role="alert">{translateError}</p>}

          <div className={styles.actions}>
            <button type="button" className={styles.btnPrimary} onClick={generate} disabled={translating}>
              {translating ? "Generating…" : "Generate"}
            </button>
            <button type="button" className={styles.btnGhost} onClick={goBack}>
              Back
            </button>
          </div>
        </section>
      )}

      {step === "reviewing-translation" && translateResult && (
        <section>
          <div className={styles.card}>
            <div className={styles.cardHeaderRow}>
              <div className={styles.cardTitle}>Patient-Friendly Explanation</div>
              <button
                type="button"
                className={styles.linkBtn}
                onClick={() => setEditingManually((prev) => !prev)}
              >
                {editingManually ? "✓ Done editing" : "✎ Edit manually"}
              </button>
            </div>
            <div className={styles.cardAccent} />
            {editingManually ? (
              <textarea
                className={styles.textarea}
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
              />
            ) : (
              <div className={styles.docExplanation}>
                <p dir="auto">{editedText}</p>
              </div>
            )}
          </div>

          <div className={styles.card}>
            <div className={styles.cardTitle}>Selected Terms</div>
            <div className={styles.cardAccent} />
            <ul className={styles.checklist}>
              {translateResult.explained_terms_list.map((term) => (
                <li key={term}>{term}</li>
              ))}
            </ul>
          </div>

          <div className={styles.actions}>
            <button type="button" className={styles.btnPrimary} onClick={approveTranslation}>
              Approve &amp; Export →
            </button>
            <button type="button" className={styles.btnGhost} onClick={backToTerms}>
              Back
            </button>
          </div>
        </section>
      )}

      {step === "result" && translateResult && (
        <section>
          <div className={styles.docSuccessIcon}>✓</div>
          <p className={styles.docSuccessText}>The patient-friendly version is ready.</p>

          <div className={styles.docFrame}>
            {renderDocContent()}
          </div>

          <div className={styles.actions}>
            <button type="button" className={styles.btnPrimary} onClick={printDoc}>
              Print
            </button>
            <button type="button" className={styles.btnGhost} onClick={startOver}>
              Start New Visit
            </button>
          </div>

          {createPortal(
            <div className={`${styles.docFrame} clearmed-print-portal`}>{renderDocContent()}</div>,
            document.body,
          )}
        </section>
      )}
    </div>
  );
}
