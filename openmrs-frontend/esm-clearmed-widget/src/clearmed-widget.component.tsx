import React, { useState } from "react";
import { useConfig } from "@openmrs/esm-framework";
import {
  analyseText,
  translateText,
  type AnalyseResponse,
  type TranslateResponse,
} from "./clearmed-api";
import type { ConfigSchema } from "./config-schema";
import logo from "./assets/logo-symbol.png";
import styles from "./clearmed-widget.scss";

interface ClearmedWidgetProps {
  patientUuid: string;
}

type Step = "writing-notes" | "reviewing-terms" | "result";

function combineNoteText(visitNotes: string, recommendation: string): string {
  return `Visit notes:\n${visitNotes}\n\nRecommendation & medication:\n${recommendation}`;
}

// Mirrors static/script.js's sentencesOf() so the generated document reads
// the same way as the standalone wizard's: one <p> per sentence.
function sentencesOf(text: string): string[] {
  const parts = text.match(/[^.!?]+[.!?]*/g);
  return parts ? parts.map((s) => s.trim()).filter(Boolean) : [text];
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
  const [exportingPdf, setExportingPdf] = useState(false);

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
      setStep("result");
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
  };

  // Writes the PDF with jsPDF's native text API (doc.text/splitTextToSize)
  // instead of doc.html() -- doc.html() rasterizes the live DOM to a canvas,
  // which is both slow (a full render pass) and produces uneven letter
  // spacing since the text is no longer real vector PDF text at that point.
  // Native text is fast and correctly kerned. The exported PDF intentionally
  // skips the small logo image (kept on-screen only) to avoid an async
  // image-loading step for something this minor.
  const exportPdf = async (translated: TranslateResponse) => {
    setExportingPdf(true);
    try {
      const { jsPDF } = await import("jspdf");
      const doc = new jsPDF({ unit: "pt", format: "letter" });

      const marginX = 40;
      const marginTop = 50;
      const marginBottom = 50;
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const contentWidth = pageWidth - marginX * 2;
      let y = marginTop;

      const ensureSpace = (lineHeight: number) => {
        if (y + lineHeight > pageHeight - marginBottom) {
          doc.addPage();
          y = marginTop;
        }
      };

      const writeParagraph = (
        text: string,
        opts: {
          fontSize?: number;
          style?: "normal" | "bold" | "italic";
          lineHeight?: number;
          color?: [number, number, number];
          spacingAfter?: number;
        } = {},
      ) => {
        const fontSize = opts.fontSize ?? 11;
        const style = opts.style ?? "normal";
        const lineHeight = opts.lineHeight ?? fontSize * 1.4;
        const color = opts.color ?? [30, 41, 59];
        const spacingAfter = opts.spacingAfter ?? 10;

        doc.setFont("helvetica", style);
        doc.setFontSize(fontSize);
        doc.setTextColor(color[0], color[1], color[2]);
        const lines: string[] = doc.splitTextToSize(text, contentWidth);
        lines.forEach((line) => {
          ensureSpace(lineHeight);
          doc.text(line, marginX, y);
          y += lineHeight;
        });
        y += spacingAfter;
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.setTextColor(100, 116, 139);
      doc.text("ClearMed", marginX, y);
      doc.text(today, pageWidth - marginX, y, { align: "right" });
      y += 24;

      writeParagraph("Patient-Friendly Summary", { fontSize: 16, style: "bold", spacingAfter: 14 });

      sentencesOf(translated.translated_text).forEach((sentence) => {
        writeParagraph(sentence, { spacingAfter: 8 });
      });

      y += 6;
      writeParagraph("Original Notes", { style: "bold", spacingAfter: 6 });
      writeParagraph(combinedText, { fontSize: 9, lineHeight: 12, color: [51, 65, 85], spacingAfter: 14 });

      writeParagraph("Selected Terms", { style: "bold", spacingAfter: 6 });
      translated.explained_terms_list.forEach((term) => {
        writeParagraph(`• ${term}`, { fontSize: 10, spacingAfter: 4 });
      });

      y += 10;
      writeParagraph(
        "Term explanations are sourced from MedlinePlus, a service of the U.S. National Library of " +
          "Medicine (NIH), and were shortened and summarized with the help of AI for readability. This " +
          "document is not a substitute for professional medical advice.",
        { fontSize: 8, lineHeight: 11, color: [100, 116, 139] },
      );

      doc.save("clearmed-summary.pdf");
    } finally {
      setExportingPdf(false);
    }
  };

  const printDoc = () => {
    window.print();
  };

  const combinedText = combineNoteText(visitNotes, recommendation);
  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

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
                    {term.main_term}
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

      {step === "result" && translateResult && (
        <section>
          <div className={`${styles.docFrame} clearmed-print-doc`}>
            <div className={styles.docSuccessIcon}>✓</div>
            <p className={styles.docSuccessText}>The patient-friendly version is ready.</p>

            <div className={styles.docHeader}>
              <img src={logo} alt="ClearMed" className={styles.docLogo} />
              <span className={styles.docDate}>{today}</span>
            </div>
            <h3 className={styles.docTitle}>Patient-Friendly Summary</h3>

            <div className={styles.docExplanation}>
              {sentencesOf(translateResult.translated_text).map((sentence, i) => (
                <p key={i}>{sentence}</p>
              ))}
            </div>

            <div className={styles.docOriginal}>
              <h4>Original Notes</h4>
              <pre>{combinedText}</pre>
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
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={() => exportPdf(translateResult)}
              disabled={exportingPdf}
            >
              {exportingPdf ? "Exporting…" : "Export PDF"}
            </button>
            <button type="button" className={styles.btnGhost} onClick={printDoc}>
              Print
            </button>
            <button type="button" className={styles.btnGhost} onClick={startOver}>
              Start New Document
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
