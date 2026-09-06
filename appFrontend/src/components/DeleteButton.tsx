import { useState } from "react";

interface DeletionImpact {
  documentCount: number;
  subfolderCount: number;
}

function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

// Reusable danger-zone action for the single document/folder currently being
// viewed (same placement pattern as TermsButton) -- not a per-row list icon.
// The UI text adapts to `type`; the actual delete call is entirely owned by
// the caller via onDelete, which must call the real backend endpoint.
export default function DeleteButton({ type, name, onDelete, getDeletionImpact }: {
  type: "document" | "folder";
  name: string;
  // Deletes the real document/folder via the existing API. Throwing keeps
  // the confirmation modal open with the error shown, so the user can
  // retry without the item ever disappearing from the UI before the
  // backend actually confirms deletion.
  onDelete: () => Promise<void>;
  // Folder-only: fetches the real, recursive count of documents/subfolders
  // this folder contains, so the confirmation can show the actual impact of
  // a cascading delete instead of just blocking it. Ignored for documents.
  getDeletionImpact?: () => Promise<DeletionImpact>;
}) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [impact, setImpact] = useState<DeletionImpact | null>(null);
  const [loadingImpact, setLoadingImpact] = useState(false);

  const label = type === "folder" ? "Folder" : "Document";

  function handleOpen() {
    setOpen(true);
    setError(null);
    setImpact(null);
    if (type === "folder" && getDeletionImpact) {
      setLoadingImpact(true);
      getDeletionImpact()
        .then(setImpact)
        // Best-effort: the delete call itself still recurses correctly on
        // the backend even if this preview fails to load -- worst case the
        // user just sees the generic warning instead of the exact counts.
        .catch(() => setImpact(null))
        .finally(() => setLoadingImpact(false));
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await onDelete();
      // success: the caller navigates away, so there's nothing left to close here
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not delete this ${label.toLowerCase()}. Please try again.`);
      setDeleting(false);
    }
  }

  const hasContents = impact !== null && (impact.documentCount > 0 || impact.subfolderCount > 0);

  return (
    <>
      <button
        onClick={handleOpen}
        style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "10px 18px", background: "#fff", color: "#D96B6B",
          border: "1.5px solid #F0DADA", borderRadius: 12, cursor: "pointer",
          fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600,
          boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
        }}
      >
        <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
          <polyline points="3 6 5 6 21 6" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
          <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
          <path d="M10 11v6M14 11v6" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
          <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
        </svg>
        Delete {label}
      </button>

      {/* Confirmation modal */}
      {open && (
        <div
          onClick={() => !deleting && setOpen(false)}
          style={{
            position: "fixed", inset: 0, background: "rgba(44,36,32,0.45)",
            zIndex: 1000, display: "flex", alignItems: "flex-end", justifyContent: "center",
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: "#F9F7F5", borderRadius: "24px 24px 0 0",
              width: "100%", maxWidth: 480, padding: "20px 20px calc(env(safe-area-inset-bottom) + 24px)",
              boxShadow: "0 -4px 32px rgba(0,0,0,0.12)",
              animation: "slideUp 0.22s ease-out",
            }}
          >
            <style>{`@keyframes slideUp { from { transform: translateY(40px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }`}</style>

            <div style={{ width: 36, height: 4, borderRadius: 2, background: "#C4BDB9", margin: "0 auto 20px" }} />

            {/* Icon */}
            <div style={{ width: 52, height: 52, borderRadius: 16, background: "#FDF0F0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
              <svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                <polyline points="3 6 5 6 21 6" stroke="#D96B6B" strokeWidth={1.8} strokeLinecap="round" />
                <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" stroke="#D96B6B" strokeWidth={1.8} strokeLinecap="round" />
                <path d="M10 11v6M14 11v6" stroke="#D96B6B" strokeWidth={1.8} strokeLinecap="round" />
                <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" stroke="#D96B6B" strokeWidth={1.8} strokeLinecap="round" />
              </svg>
            </div>

            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 18, fontWeight: 700, color: "#2C2420", textAlign: "center", marginBottom: 8 }}>Delete {label}?</p>

            {loadingImpact && (
              <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390", textAlign: "center", marginBottom: 12 }}>Checking folder contents…</p>
            )}

            {!loadingImpact && hasContents && impact && (
              <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, color: "#D96B6B", textAlign: "center", lineHeight: 1.6, marginBottom: 12, background: "#FDF0F0", borderRadius: 11, padding: "10px 14px" }}>
                <span style={{ fontWeight: 600, color: "#2C2420" }}>{name}</span> contains {pluralize(impact.documentCount, "document")}
                {impact.subfolderCount > 0 ? ` and ${pluralize(impact.subfolderCount, "sub-folder")}` : ""}.
                All of them will be permanently deleted along with this folder.
              </p>
            )}

            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 14, color: "#9B9390", textAlign: "center", lineHeight: 1.6, marginBottom: error ? 14 : 28 }}>
              {!hasContents && <span style={{ fontWeight: 600, color: "#2C2420" }}>{name}</span>}
              {!hasContents && " will be permanently deleted. "}
              This action cannot be undone.
            </p>
            {error && <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#D96B6B", textAlign: "center", marginBottom: 14 }}>{error}</p>}

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <button
                onClick={handleDelete}
                disabled={deleting}
                style={{
                  width: "100%", padding: "15px", border: "none", borderRadius: 13,
                  background: deleting ? "#E8A0A0" : "#D96B6B", color: "#fff",
                  fontFamily: "Outfit, sans-serif", fontSize: 16, fontWeight: 600,
                  cursor: deleting ? "not-allowed" : "pointer", transition: "background 0.2s",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                }}
              >
                {deleting
                  ? <><div style={{ width: 18, height: 18, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />Deleting…</>
                  : "Yes, Delete"}
              </button>
              <button
                onClick={() => setOpen(false)}
                disabled={deleting}
                style={{
                  width: "100%", padding: "15px", border: "1.5px solid #EDE9E5", borderRadius: 13,
                  background: "#fff", color: "#6B6460",
                  fontFamily: "Outfit, sans-serif", fontSize: 16, fontWeight: 600,
                  cursor: deleting ? "not-allowed" : "pointer",
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}
