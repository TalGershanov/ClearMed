import type { CSSProperties } from "react";

export const inputStyle: CSSProperties = {
  width: "100%", padding: "12px 13px", fontFamily: "Outfit, sans-serif", fontSize: 15,
  color: "#2C2420", background: "#fff", border: "1.5px solid #EDE9E5", borderRadius: 11, outline: "none",
};

export function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
