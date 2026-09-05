import { useState } from "react";
import type { ApiDocument, ApiDocumentDetail } from "@/types";
import { Field } from "@/components/Field";
import { NoteIcon, PDFIcon, ScanDocIcon, ShareIcon, SparkIcon } from "@/components/icons";
import { formatFileSize, inputStyle } from "@/lib/ui";

// The "Original" tab shows real extracted text (Phase 4). "Plain Language"
// has no real ClearMed processing yet -- it always shows an honest
// not-processed placeholder, never a fake simplification.
function extractionPlaceholderMessage(status: ApiDocumentDetail["extraction_status"]): string {
  switch (status) {
    case "no_text_found":
      return "This document appears to be scanned and requires OCR to extract text.";
    case "failed":
      return "Text extraction failed for this document.";
    case "extracted":
      return "";
    case "pending":
    default:
      return "Text extraction is not available for this document yet.";
  }
}

export function DocumentDetailScreen({ doc, detail }: { doc: ApiDocument; detail: ApiDocumentDetail | null }) {
  const [tab, setTab] = useState<"original" | "plain">("original");
  const [note, setNote] = useState("");
  const [showNotes, setShowNotes] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [shareEmail, setShareEmail] = useState("");

  const typeLabel = doc.mime_type === "application/pdf" ? "PDF"
    : doc.mime_type === "image/jpeg" ? "JPEG image"
    : doc.mime_type === "image/png" ? "PNG image"
    : doc.mime_type;
  const uploadedLabel = new Date(doc.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

  function renderOriginalTab() {
    if (!detail) {
      return <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390" }}>Loading…</p>;
    }
    if (detail.extraction_status === "extracted" && detail.original_text) {
      return (
        <div style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#2C2420", lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 420, overflowY: "auto" }}>
          {detail.original_text}
        </div>
      );
    }
    return (
      <div style={{ background: "#F9F7F5", borderRadius: 11, padding: "14px 16px", display: "flex", gap: 10, alignItems: "flex-start" }}>
        <div style={{ marginTop: 2 }}><SparkIcon /></div>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#6B6460", lineHeight: 1.6 }}>
          {extractionPlaceholderMessage(detail.extraction_status)}
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: "0 16px 40px", maxWidth: 480, margin: "0 auto" }}>
      {/* Action strip */}
      <div style={{ display: "flex", gap: 8, paddingTop: 16, paddingBottom: 14, overflowX: "auto", scrollbarWidth: "none" }}>
        {[
          { label: "Notes", icon: <NoteIcon />, action: () => setShowNotes(v => !v) },
          { label: "Share", icon: <ShareIcon />, action: () => setShowShare(v => !v) },
        ].map(({ label, icon, action }) => (
          <button key={label} onClick={action} style={{ flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: 5, padding: "11px 14px", background: "#fff", border: "1.5px solid #EDE9E5", borderRadius: 13, cursor: "pointer", fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 500, color: "#7BAAC8", minWidth: 68 }}>
            {icon}{label}
          </button>
        ))}
      </div>

      {/* Metadata header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <div style={{ width: 42, height: 42, borderRadius: 11, background: "rgba(224,123,85,0.10)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          {doc.mime_type === "application/pdf" ? <PDFIcon color="#E07B55" /> : <ScanDocIcon color="#E07B55" />}
        </div>
        <div style={{ minWidth: 0 }}>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 16, fontWeight: 700, color: "#2C2420", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{doc.name}</p>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390" }}>{typeLabel} · {formatFileSize(doc.file_size)} · Uploaded {uploadedLabel}</p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", background: "#EDE9E5", borderRadius: 11, padding: 3, marginBottom: 16 }}>
        {(["original", "plain"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: "8px", borderRadius: 8, border: "none", background: tab === t ? "#fff" : "transparent", fontFamily: "Outfit, sans-serif", fontSize: 12, fontWeight: 600, color: tab === t ? "#2C2420" : "#9B9390", cursor: "pointer", transition: "all 0.15s", boxShadow: tab === t ? "0 1px 3px rgba(0,0,0,0.08)" : "none" }}>
            {t === "original" ? "Original" : "Plain Language"}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ background: "#fff", borderRadius: 18, padding: 18, minHeight: 120, boxShadow: "0 1px 4px rgba(0,0,0,0.05)", marginBottom: 14 }}>
        {tab === "original" ? renderOriginalTab() : (
          <div style={{ background: "#F9F7F5", borderRadius: 11, padding: "14px 16px", display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ marginTop: 2 }}><SparkIcon /></div>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#6B6460", lineHeight: 1.6 }}>
              Not processed yet — ClearMed plain-language summaries aren't available until a later phase.
            </p>
          </div>
        )}
      </div>

      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 11, color: "#C4BDB9", marginBottom: 14 }}>Original file: {doc.original_filename}</p>

      {/* Notes */}
      {showNotes && (
        <div style={{ background: "#fff", borderRadius: 18, padding: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.05)", marginBottom: 14 }}>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 700, color: "#2C2420", marginBottom: 10 }}>Notes</p>
          <textarea value={note} onChange={e => setNote(e.target.value)} placeholder="Add personal notes…" rows={4} style={{ width: "100%", padding: "11px 13px", fontFamily: "Outfit, sans-serif", fontSize: 14, color: "#2C2420", background: "#F9F7F5", border: "1.5px solid #EDE9E5", borderRadius: 11, resize: "none", outline: "none" }} />
          <button style={{ marginTop: 10, padding: "9px 20px", background: "#7BAAC8", color: "#fff", border: "none", borderRadius: 9, fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Save note</button>
        </div>
      )}

      {/* Share */}
      {showShare && (
        <div style={{ background: "#fff", borderRadius: 18, padding: 16, boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 700, color: "#2C2420", marginBottom: 10 }}>Share with contact</p>
          <Field label="Recipient email">
            <input type="email" value={shareEmail} onChange={e => setShareEmail(e.target.value)} placeholder="doctor@clinic.com" style={inputStyle} />
          </Field>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button style={{ flex: 1, padding: "10px", background: "#E07B55", color: "#fff", border: "none", borderRadius: 9, fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Send document</button>
            <button style={{ padding: "10px 14px", background: "#F9F7F5", color: "#7BAAC8", border: "1.5px solid #EDE9E5", borderRadius: 9, fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Copy link</button>
          </div>
        </div>
      )}
    </div>
  );
}
