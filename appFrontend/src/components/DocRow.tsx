import type { Doc } from "@/types";
import { ChevronIcon, PDFIcon, ScanDocIcon } from "@/components/icons";

// Renders a mock search-result row (Library search box only -- see USER_DOCS
// in App.tsx). Distinct from DocumentRow, which renders real backend documents.
export function DocRow({ doc, onOpen, showFolder }: { doc: Doc; onOpen: (d: Doc) => void; showFolder?: boolean }) {
  return (
    <button onClick={() => onOpen(doc)} style={{ width: "100%", background: "#fff", border: "none", borderRadius: 14, padding: "13px 14px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer", textAlign: "left", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
      <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: doc.type === "Scan" ? "rgba(123,170,200,0.14)" : "rgba(224,123,85,0.10)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        {doc.type === "Scan" ? <ScanDocIcon color="#7BAAC8" /> : <PDFIcon color="#E07B55" />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600, color: "#2C2420", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{doc.name}</p>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390" }}>{showFolder ? `${doc.folder} · ` : ""}{doc.date}</p>
      </div>
      {doc.translated && <span style={{ flexShrink: 0, fontSize: 10, fontWeight: 600, fontFamily: "Outfit, sans-serif", background: "rgba(123,170,200,0.15)", color: "#7BAAC8", padding: "3px 8px", borderRadius: 6 }}>Translated</span>}
      <ChevronIcon />
    </button>
  );
}
