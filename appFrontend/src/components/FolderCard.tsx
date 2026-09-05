import type { ApiFolder } from "@/types";
import { styleForFolder } from "@/lib/folderStyle";
import { ChevronIcon, FolderFillIcon } from "@/components/icons";

export function FolderCard({ folder, docCount, onClick }: { folder: ApiFolder; docCount: number; onClick: () => void }) {
  const fs = styleForFolder(folder);
  return (
    <button onClick={onClick} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", background: "#fff", border: "none", borderRadius: 16, cursor: "pointer", textAlign: "left", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", width: "100%" }}>
      <div style={{ width: 46, height: 46, borderRadius: 13, background: fs.image ? "#000" : fs.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, overflow: "hidden" }}>
        {fs.image ? <img src={fs.image} style={{ width: "100%", height: "100%", objectFit: "cover" }} alt={folder.name} /> : <FolderFillIcon color={fs.color} />}
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 15, fontWeight: 700, color: "#2C2420", marginBottom: 2 }}>{folder.name}</p>
        <p style={{ fontFamily: "Outfit, sans-serif", fontSize: 12, color: "#9B9390" }}>{docCount} item{docCount !== 1 ? "s" : ""}</p>
      </div>
      <ChevronIcon />
    </button>
  );
}
