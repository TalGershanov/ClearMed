import type { ApiDocument } from "@/types";
import { formatFileSize } from "@/lib/ui";
import { ChevronIcon, PDFIcon, ScanDocIcon } from "@/components/icons";

// Renders a real backend document (folder listings) -- see DocRow for the
// separate mock-search-result row.
export function DocumentRow({ document, onOpen }: { document: ApiDocument; onOpen: () => void }) {
  const isPdf = document.mime_type === "application/pdf";
  return (
    <button onClick={onOpen} style={{ width: "100%", background: "#fff", border: "none", borderRadius: 14, padding: "13px 14px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer", textAlign: "left", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
      <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: isPdf ? "rgba(224,123,85,0.10)" : "rgba(123,170,200,0.14)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        {isPdf ? <PDFIcon color="#E07B55" /> : <ScanDocIcon color="#7BAAC8" />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600, color: "#2C2420", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{document.name}</p>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390" }}>{formatFileSize(document.file_size)} · {new Date(document.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</p>
      </div>
      <ChevronIcon />
    </button>
  );
}
