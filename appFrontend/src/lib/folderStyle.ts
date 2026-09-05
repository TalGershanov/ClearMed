import type { FolderStyle } from "@/types";

export const FOLDER_PALETTE: FolderStyle[] = [
  { bg: "rgba(224,123,85,0.12)",  color: "#E07B55" },
  { bg: "rgba(123,170,200,0.14)", color: "#7BAAC8" },
  { bg: "rgba(107,170,122,0.13)", color: "#6BAA7A" },
  { bg: "rgba(155,120,200,0.12)", color: "#9B78C8" },
  { bg: "rgba(155,138,120,0.12)", color: "#9B8A78" },
  { bg: "rgba(200,160,100,0.13)", color: "#C8A064" },
  { bg: "rgba(100,160,180,0.13)", color: "#64A0B4" },
];

// Preserves the curated look of the 5 backend-seeded default folders even
// though the backend itself stores no color for them (color is optional).
export const FOLDER_META: Record<string, FolderStyle> = {
  "Lab Results":   FOLDER_PALETTE[0],
  "Imaging":       FOLDER_PALETTE[1],
  "Prescriptions": FOLDER_PALETTE[2],
  "Surgery":       FOLDER_PALETTE[3],
  "General":       FOLDER_PALETTE[4],
};

export const COLOR_OPTIONS = [
  { color: "#E07B55", bg: "rgba(224,123,85,0.12)" },
  { color: "#7BAAC8", bg: "rgba(123,170,200,0.14)" },
  { color: "#6BAA7A", bg: "rgba(107,170,122,0.13)" },
  { color: "#9B78C8", bg: "rgba(155,120,200,0.12)" },
  { color: "#C8A064", bg: "rgba(200,160,100,0.13)" },
  { color: "#D96B8A", bg: "rgba(217,107,138,0.12)" },
  { color: "#64A0B4", bg: "rgba(100,160,180,0.13)" },
  { color: "#9B8A78", bg: "rgba(155,138,120,0.12)" },
];

// Derives the visual swatch for a real backend folder: matches its stored
// hex `color` against the known swatches, falls back to the curated default
// (by name) for the 5 seeded folders, then to a stable hash -- same fallback
// formula the original mock used, just driven by backend data now.
export function styleForFolder(folder: { name: string; color: string | null; cover_image_path: string | null }): FolderStyle {
  if (folder.cover_image_path) {
    return { bg: "#000", color: "#fff", image: folder.cover_image_path };
  }
  if (folder.color) {
    const match = COLOR_OPTIONS.find(opt => opt.color === folder.color);
    if (match) return match;
  }
  if (FOLDER_META[folder.name]) return FOLDER_META[folder.name];
  return FOLDER_PALETTE[Math.abs(folder.name.split("").reduce((a, c) => a + c.charCodeAt(0), 0)) % FOLDER_PALETTE.length];
}
