import { useState } from "react";
import type { ApiFolder, Doc } from "@/types";
import { DocRow } from "@/components/DocRow";
import { EmptyMsg } from "@/components/EmptyMsg";
import { FolderCard } from "@/components/FolderCard";
import { NewFolderForm } from "@/components/NewFolderForm";
import { PlusIcon, SearchIcon } from "@/components/icons";
import { inputStyle } from "@/lib/ui";

export function LibraryScreen({ docs, folders, onOpenFolder, onCreateFolder }: {
  docs: Doc[]; folders: ApiFolder[];
  onOpenFolder: (folder: ApiFolder) => void;
  onCreateFolder: (name: string, color: string) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [showNew, setShowNew] = useState(false);
  const searchActive = search.trim().length > 0;
  const allFiltered = searchActive ? docs.filter(d => d.name.toLowerCase().includes(search.toLowerCase())) : [];

  return (
    <div style={{ padding: "16px 16px 100px", maxWidth: 480, margin: "0 auto" }}>
      <div style={{ position: "relative", marginBottom: 16 }}>
        <span style={{ position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)", color: "#C4BDB9" }}><SearchIcon /></span>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search all documents…" style={{ ...inputStyle, paddingLeft: 40 }} />
      </div>
      {searchActive ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390", marginBottom: 4 }}>{allFiltered.length} result{allFiltered.length !== 1 ? "s" : ""}</p>
          {allFiltered.length === 0 && <EmptyMsg text="No documents found" />}
          {allFiltered.map(doc => <DocRow key={doc.id} doc={doc} onOpen={() => {}} showFolder />)}
        </div>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, fontWeight: 600, color: "#9B9390", letterSpacing: 0.5, textTransform: "uppercase" }}>Folders</p>
            <button onClick={() => setShowNew(v => !v)} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 13px", background: "#E07B55", color: "#fff", border: "none", borderRadius: 9, fontFamily: "Outfit, sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              <PlusIcon /> New folder
            </button>
          </div>
          {showNew && (
            <NewFolderForm
              onCreate={async (name, color) => {
                await onCreateFolder(name, color);
                setShowNew(false);
              }}
              onCancel={() => setShowNew(false)}
            />
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {folders.length === 0 && !showNew && <EmptyMsg text="No folders yet" />}
            {folders.map(folder => (
              <FolderCard key={folder.id} folder={folder} docCount={docs.filter(d => d.folder === folder.name).length} onClick={() => onOpenFolder(folder)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
