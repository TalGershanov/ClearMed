import { useState } from "react";
import type { ApiDocument, ApiFolder, ApiFolderDetail } from "@/types";
import { DocumentRow } from "@/components/DocumentRow";
import { EmptyMsg } from "@/components/EmptyMsg";
import { FolderCard } from "@/components/FolderCard";
import { NewFolderForm } from "@/components/NewFolderForm";
import { FolderPlusIcon } from "@/components/icons";

export function FolderScreen({ folder, onOpenFolder, onOpenDoc, onCreateFolder }: {
  folder: ApiFolderDetail;
  onOpenFolder: (folder: ApiFolder) => void;
  onOpenDoc: (document: ApiDocument) => void;
  onCreateFolder: (name: string, color: string) => Promise<void>;
}) {
  const [showNewFolder, setShowNewFolder] = useState(false);

  const subfolders = folder.children;
  const documents = folder.documents;
  const isEmpty = subfolders.length === 0 && documents.length === 0;

  return (
    <div style={{ padding: "16px 16px 40px", maxWidth: 480, margin: "0 auto" }}>
      {/* Action row */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={() => setShowNewFolder(v => !v)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "9px 14px", background: showNewFolder ? "#2C2420" : "#E07B55", color: "#fff", border: "none", borderRadius: 10, fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          <FolderPlusIcon /> New folder
        </button>
      </div>

      {/* New subfolder form */}
      {showNewFolder && (
        <NewFolderForm
          onCreate={async (name, color) => {
            await onCreateFolder(name, color);
            setShowNewFolder(false);
          }}
          onCancel={() => setShowNewFolder(false)}
        />
      )}

      {isEmpty && !showNewFolder && <EmptyMsg text="This folder is empty. Add a subfolder, or upload a document from the Upload tab." />}

      {/* Subfolders */}
      {subfolders.length > 0 && (
        <>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 600, color: "#9B9390", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 10 }}>Folders</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 18 }}>
            {subfolders.map(sub => (
              <FolderCard key={sub.id} folder={sub} docCount={0} onClick={() => onOpenFolder(sub)} />
            ))}
          </div>
        </>
      )}

      {/* Documents -- real backend data */}
      {documents.length > 0 && (
        <>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 600, color: "#9B9390", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 10 }}>Documents</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {documents.map(document => <DocumentRow key={document.id} document={document} onOpen={() => onOpenDoc(document)} />)}
          </div>
        </>
      )}
    </div>
  );
}
