import type { Screen } from "@/types";
import { FolderNavIcon, LogoutIcon, UploadNavIcon } from "@/components/icons";

export function BottomNav({ active, onNavigate, onLogout }: { active: "upload" | "library"; onNavigate: (s: Screen) => void; onLogout: () => void }) {
  return (
    <nav style={{ background: "#fff", borderTop: "1px solid #EDE9E5", display: "flex", flexShrink: 0 }}>
      {([
        { key: "library", Icon: FolderNavIcon, label: "Documents" },
        { key: "upload",  Icon: UploadNavIcon, label: "Upload" },
      ] as const).map(({ key, Icon, label }) => (
        <button
          key={key}
          onClick={() => onNavigate(key)}
          style={{
            flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
            padding: "11px 0 14px", background: "none", border: "none", cursor: "pointer",
            color: active === key ? "#E07B55" : "#9B9390",
            fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 500, transition: "color 0.15s",
          }}
        >
          <Icon active={active === key} />
          {label}
        </button>
      ))}
      <button
        onClick={onLogout}
        style={{
          flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
          padding: "11px 0 14px", background: "none", border: "none", cursor: "pointer",
          color: "#9B9390", fontFamily: "Outfit, sans-serif", fontSize: 11, fontWeight: 500,
        }}
      >
        <LogoutIcon />
        Log out
      </button>
    </nav>
  );
}
