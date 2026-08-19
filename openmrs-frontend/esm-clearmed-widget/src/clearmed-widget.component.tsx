import React, { useState } from "react";
import { useConfig } from "@openmrs/esm-framework";
import { analyseText, type AnalyseResponse } from "./clearmed-api";
import type { ConfigSchema } from "./config-schema";

export default function ClearmedWidget() {
  const config = useConfig<ConfigSchema>();
  const [result, setResult] = useState<AnalyseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyse = async (text: string) => {
    setError(null);
    try {
      const response = await analyseText(config.clearmedApiBaseUrl, text);
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  };

  return (
    <div>
      <h4>ClearMed</h4>
      {error && <p role="alert">{error}</p>}
      {result && (
        <ul>
          {(result.detected_terms ?? []).map((term) => (
            <li key={term.main_term}>{term.main_term}</li>
          ))}
        </ul>
      )}
      {/* Wire handleAnalyse up to a real input / patient-chart data source */}
    </div>
  );
}
