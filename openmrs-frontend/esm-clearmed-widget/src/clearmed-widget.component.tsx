import React, { useEffect, useState } from "react";
import { useConfig } from "@openmrs/esm-framework";
import {
  analyseText,
  fetchPatientNotes,
  translateText,
  type AnalyseResponse,
  type PatientNote,
  type TranslateResponse,
} from "./clearmed-api";
import type { ConfigSchema } from "./config-schema";

interface ClearmedWidgetProps {
  patientUuid: string;
}

type Step = "picking-note" | "reviewing-terms" | "result";

export default function ClearmedWidget({ patientUuid }: ClearmedWidgetProps) {
  const config = useConfig<ConfigSchema>();
  const { clearmedApiBaseUrl } = config;

  const [step, setStep] = useState<Step>("picking-note");

  const [notes, setNotes] = useState<PatientNote[] | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);

  const [selectedNote, setSelectedNote] = useState<PatientNote | null>(null);
  const [analyseResult, setAnalyseResult] = useState<AnalyseResponse | null>(null);
  const [analyseError, setAnalyseError] = useState<string | null>(null);

  const [uiSelection, setUiSelection] = useState<Record<string, boolean>>({});
  const [translateResult, setTranslateResult] = useState<TranslateResponse | null>(null);
  const [translateError, setTranslateError] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setNotes(null);
    setNotesError(null);
    fetchPatientNotes(clearmedApiBaseUrl, patientUuid)
      .then((fetched) => {
        if (!cancelled) setNotes(fetched);
      })
      .catch((e) => {
        if (!cancelled) setNotesError(e instanceof Error ? e.message : "Unknown error");
      });
    return () => {
      cancelled = true;
    };
  }, [clearmedApiBaseUrl, patientUuid]);

  const pickNote = async (note: PatientNote) => {
    setSelectedNote(note);
    setAnalyseError(null);
    setAnalyseResult(null);
    try {
      const result = await analyseText(clearmedApiBaseUrl, note.note_text);
      setAnalyseResult(result);
      setUiSelection(result.ui_selection);
      setStep("reviewing-terms");
    } catch (e) {
      setAnalyseError(e instanceof Error ? e.message : "Unknown error");
    }
  };

  const toggleTerm = (term: string) => {
    setUiSelection((prev) => ({ ...prev, [term]: !prev[term] }));
  };

  const generate = async () => {
    if (!selectedNote) return;
    setTranslating(true);
    setTranslateError(null);
    try {
      const result = await translateText(clearmedApiBaseUrl, selectedNote.note_text, uiSelection);
      setTranslateResult(result);
      setStep("result");
    } catch (e) {
      setTranslateError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setTranslating(false);
    }
  };

  const startOver = () => {
    setStep("picking-note");
    setSelectedNote(null);
    setAnalyseResult(null);
    setAnalyseError(null);
    setUiSelection({});
    setTranslateResult(null);
    setTranslateError(null);
  };

  return (
    <div>
      <h3>ClearMed</h3>

      {step === "picking-note" && (
        <section>
          <h4>Choose a clinical note to translate</h4>
          {notesError && <p role="alert">{notesError}</p>}
          {!notesError && notes === null && <p>Loading notes…</p>}
          {!notesError && notes !== null && notes.length === 0 && <p>No clinical notes found for this patient.</p>}
          {!notesError && notes !== null && notes.length > 0 && (
            <ul>
              {notes.map((note) => (
                <li key={note.obs_uuid}>
                  <button type="button" onClick={() => pickNote(note)}>
                    <strong>{note.obs_datetime ?? "Unknown date"}</strong>
                    {" — "}
                    {note.note_text.slice(0, 120)}
                    {note.note_text.length > 120 ? "…" : ""}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {analyseError && <p role="alert">{analyseError}</p>}
        </section>
      )}

      {step === "reviewing-terms" && analyseResult && (
        <section>
          <h4>Select terms to explain</h4>
          <ul>
            {analyseResult.detected_terms.map((term) => (
              <li key={term.main_term}>
                <label>
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
          {translateError && <p role="alert">{translateError}</p>}
          <button type="button" onClick={generate} disabled={translating}>
            {translating ? "Generating…" : "Generate"}
          </button>
          <button type="button" onClick={startOver}>
            Start over
          </button>
        </section>
      )}

      {step === "result" && translateResult && (
        <section>
          <h4>Result</h4>
          <p>{translateResult.translated_text}</p>
          <button type="button" onClick={startOver}>
            Start over
          </button>
        </section>
      )}
    </div>
  );
}
