// apply_translations (logic/translator.py) -- and, for a translated copy,
// logic/document_translation.py's Google Translate pass-through of that
// same text -- splices each approved term's explanation in as
// "<term> (<explanation>)" right after the term itself. Bolding every
// parenthesized segment highlights exactly the added explanation text,
// purely a rendering choice (the underlying string is untouched).
export function renderSimplifiedText(text: string) {
  return text.split(/(\([^()]*\))/g).map((segment, i) =>
    segment.startsWith("(") && segment.endsWith(")") ? <strong key={i}>{segment}</strong> : segment,
  );
}
