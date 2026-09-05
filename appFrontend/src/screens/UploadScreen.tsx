import { useEffect, useRef, useState } from "react";
import type { ApiFolder } from "@/types";
import { ActionTile } from "@/components/ActionTile";
import { Field } from "@/components/Field";
import { CameraIcon, CheckCircle, PDFIcon, ScanIcon, Spinner, UploadCloudIcon } from "@/components/icons";
import { formatFileSize } from "@/lib/ui";
import { inputStyle } from "@/lib/ui";
import { isAcceptedFile, MAX_UPLOAD_BYTES } from "@/lib/uploadValidation";

export function UploadScreen({ folders, onUpload }: {
  folders: ApiFolder[];
  // For a text-based PDF, this now also runs ClearMed analysis and the
  // caller navigates to Terms Found; other file types still just land in
  // the folder, exactly as before Phase 5.
  onUpload: (folder: ApiFolder, name: string, file: File) => Promise<void>;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null);
  const [docName, setDocName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Default the folder picker to the first root folder once the list loads.
  useEffect(() => {
    if (selectedFolderId === null && folders.length > 0) {
      setSelectedFolderId(folders[0].id);
    }
  }, [folders, selectedFolderId]);

  function pickFile(file: File) {
    setError(null);
    setDone(false);
    if (!isAcceptedFile(file)) {
      setError("Unsupported file type. Please choose a PDF, JPG, or PNG.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError("File is larger than 20 MB.");
      return;
    }
    setSelectedFile(file);
  }

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) pickFile(file);
  }

  async function doUpload() {
    if (uploading || !selectedFile) return;
    const folder = folders.find(f => f.id === selectedFolderId);
    if (!folder) {
      setError("Please choose a folder to save to.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await onUpload(folder, docName, selectedFile);
      setUploading(false);
      setDone(true);
      // App navigates into the destination folder shortly after this
      // resolves, unmounting this screen -- no further cleanup needed here.
    } catch (err) {
      setUploading(false);
      setError(err instanceof Error ? err.message : "Could not upload the document. Please try again.");
    }
  }

  return (
    <div style={{ padding: "20px 20px 100px", maxWidth: 480, margin: "0 auto" }}>
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) pickFile(file);
        }}
        onClick={() => fileInputRef.current?.click()}
        style={{ border: `2px dashed ${dragOver ? "#E07B55" : "#C4BDB9"}`, borderRadius: 20, padding: "36px 20px", textAlign: "center", background: dragOver ? "rgba(224,123,85,0.05)" : "#fff", transition: "all 0.2s", cursor: "pointer" }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={handleFileInputChange}
          style={{ display: "none" }}
        />
        {uploading ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <Spinner />
            <p style={{ color: "#7BAAC8", fontFamily: "Outfit, sans-serif", fontWeight: 500 }}>Uploading…</p>
          </div>
        ) : done ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <CheckCircle />
            <p style={{ color: "#7BAAC8", fontFamily: "Outfit, sans-serif", fontWeight: 600, fontSize: 15 }}>Uploaded successfully!</p>
          </div>
        ) : selectedFile ? (
          <>
            <div style={{ width: 56, height: 56, borderRadius: 16, background: "rgba(224,123,85,0.1)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
              <PDFIcon color="#E07B55" />
            </div>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 16, fontWeight: 600, color: "#2C2420", marginBottom: 4, wordBreak: "break-word" }}>{selectedFile.name}</p>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390" }}>{formatFileSize(selectedFile.size)} — tap to choose a different file</p>
          </>
        ) : (
          <>
            <div style={{ width: 56, height: 56, borderRadius: 16, background: "rgba(224,123,85,0.1)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
              <UploadCloudIcon />
            </div>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 16, fontWeight: 600, color: "#2C2420", marginBottom: 4 }}>Drop your file here</p>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#9B9390" }}>PDF, JPG, PNG up to 20 MB</p>
            <div style={{ display: "inline-block", marginTop: 16, padding: "9px 20px", background: "#E07B55", borderRadius: 10, color: "#fff", fontFamily: "Outfit, sans-serif", fontWeight: 600, fontSize: 14 }}>Browse files</div>
          </>
        )}
      </div>

      {/* Camera / scan -- not implemented yet */}
      <div style={{ marginTop: 14, display: "flex", gap: 12 }}>
        <ActionTile icon={<CameraIcon />} label="Take a photo (soon)" color="#C4BDB9" onClick={() => {}} disabled />
        <ActionTile icon={<ScanIcon />} label="Scan document (soon)" color="#C4BDB9" onClick={() => {}} disabled />
      </div>

      {error && <p style={{ marginTop: 14, fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#E07B55" }}>{error}</p>}

      {/* Folder */}
      <div style={{ marginTop: 24 }}>
        <label style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, color: "#6B6460", display: "block", marginBottom: 10 }}>Save to folder</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {folders.map(f => (
            <button key={f.id} onClick={() => setSelectedFolderId(f.id)} style={{ padding: "7px 15px", borderRadius: 20, border: selectedFolderId === f.id ? "none" : "1.5px solid #EDE9E5", background: selectedFolderId === f.id ? "#7BAAC8" : "#fff", color: selectedFolderId === f.id ? "#fff" : "#6B6460", fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 500, cursor: "pointer", transition: "all 0.15s" }}>{f.name}</button>
          ))}
          {folders.length === 0 && <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 13, color: "#C4BDB9" }}>No folders yet — create one from Documents first.</p>}
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <Field label="Document name (optional)">
          <input type="text" value={docName} onChange={e => setDocName(e.target.value)} placeholder="e.g. Blood Test – July 2025" style={inputStyle} />
        </Field>
      </div>

      <button
        onClick={doUpload}
        disabled={uploading || !selectedFile || selectedFolderId === null}
        style={{ width: "100%", marginTop: 24, padding: "14px", background: (uploading || !selectedFile) ? "#F0A888" : "#E07B55", color: "#fff", border: "none", borderRadius: 13, fontFamily: "Outfit, sans-serif", fontSize: 16, fontWeight: 600, cursor: (uploading || !selectedFile) ? "not-allowed" : "pointer" }}
      >
        Upload & Analyze
      </button>
    </div>
  );
}
