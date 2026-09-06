import { useState } from "react";
import { COLOR_OPTIONS } from "@/lib/folderStyle";
import { inputStyle } from "@/lib/ui";
import { FolderFillIcon, ImageIcon } from "@/components/icons";

// Inline form rendered from LibraryScreen (root folders) and FolderScreen
// (nested folders) -- not a standalone navigable screen.
export function NewFolderForm({ onCreate, onCancel }: {
  onCreate: (name: string, color: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [newName, setNewName] = useState("");
  const [pickedColor, setPickedColor] = useState(COLOR_OPTIONS[0]);
  const [coverImage, setCoverImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    const trimmed = newName.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreate(trimmed, pickedColor.color);
      // success: the parent screen closes this form and refreshes its list
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create folder. Please try again.");
      setSubmitting(false);
    }
  }

  function handleImagePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => setCoverImage(ev.target?.result as string);
    reader.readAsDataURL(file);
  }

  return (
    <div style={{ background: "#fff", borderRadius: 16, padding: 16, marginBottom: 14, boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }}>
      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 700, color: "#2C2420", marginBottom: 12 }}>New folder</p>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <div style={{ width: 50, height: 50, borderRadius: 13, flexShrink: 0, overflow: "hidden", background: coverImage ? "#000" : pickedColor.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {coverImage ? <img src={coverImage} style={{ width: "100%", height: "100%", objectFit: "cover" }} alt="cover" /> : <FolderFillIcon color={pickedColor.color} />}
        </div>
        <input autoFocus value={newName} onChange={e => setNewName(e.target.value)} onKeyDown={e => e.key === "Enter" && confirm()} placeholder="Folder name…" style={{ ...inputStyle, flex: 1 }} disabled={submitting} />
      </div>
      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 600, color: "#9B9390", letterSpacing: 0.4, textTransform: "uppercase", marginBottom: 8 }}>Color</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {COLOR_OPTIONS.map(opt => (
          <button key={opt.color} onClick={() => { setPickedColor(opt); setCoverImage(null); }} disabled={submitting} style={{ width: 28, height: 28, borderRadius: "50%", background: opt.color, border: pickedColor.color === opt.color && !coverImage ? "3px solid #2C2420" : "3px solid transparent", cursor: "pointer", padding: 0, flexShrink: 0 }} />
        ))}
      </div>
      <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 600, color: "#9B9390", letterSpacing: 0.4, textTransform: "uppercase", marginBottom: 8 }}>Cover image</p>
      <label style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 14px", border: "1.5px dashed #C4BDB9", borderRadius: 10, cursor: "pointer", fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#7BAAC8", fontWeight: 500 }}>
        <ImageIcon />{coverImage ? "Change image" : "Upload an image"}
        <input type="file" accept="image/*" onChange={handleImagePick} style={{ display: "none" }} disabled={submitting} />
      </label>
      {coverImage && (
        <>
          <p style={{ marginTop: 6, fontFamily: "Outfit, sans-serif", fontSize: 11, color: "#C4BDB9" }}>
            Preview only for now — cover images aren't saved yet.
          </p>
          <button onClick={() => setCoverImage(null)} style={{ marginTop: 4, background: "none", border: "none", fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390", cursor: "pointer", padding: 0 }}>Remove image</button>
        </>
      )}
      {error && <p style={{ marginTop: 10, fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#E07B55" }}>{error}</p>}
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button
          onClick={confirm}
          disabled={!newName.trim() || submitting}
          style={{ flex: 1, padding: "11px", background: "#E07B55", color: "#fff", border: "none", borderRadius: 10, fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600, cursor: !newName.trim() || submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.7 : 1 }}
        >
          {submitting ? "Creating…" : "Create folder"}
        </button>
        <button onClick={onCancel} disabled={submitting} style={{ padding: "11px 14px", background: "#F9F7F5", color: "#9B9390", border: "1.5px solid #EDE9E5", borderRadius: 10, cursor: submitting ? "not-allowed" : "pointer", fontFamily: "Outfit, sans-serif", fontSize: 14 }}>Cancel</button>
      </div>
    </div>
  );
}
