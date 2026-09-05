import type { Screen } from "@/types";
import { Logo } from "@/components/Logo";
import { BackIcon } from "@/components/icons";

export function AppBar({ screen, navPath, docName, onNavigateTo }: {
  screen: Screen; navPath: { id: number; name: string }[]; docName: string | null;
  onNavigateTo: (depth: number) => void;
}) {
  const isRoot = screen === "library" || screen === "upload";
  const showBack = screen === "folder" || screen === "document";

  // Build breadcrumb segments
  // root = depth -1, folders = depth 0..n, document at end (not clickable)
  const crumbs: { label: string; depth: number; clickable: boolean }[] = [
    { label: "Documents", depth: -1, clickable: !isRoot },
    ...navPath.map((p, i) => ({ label: p.name, depth: i, clickable: i < navPath.length - 1 || screen === "document" })),
    ...(screen === "document" && docName ? [{ label: docName, depth: -99, clickable: false }] : []),
  ];

  return (
    <div style={{
      background: "#fff", borderBottom: "1px solid #EDE9E5",
      paddingTop: "calc(env(safe-area-inset-top) + 52px)",
      paddingBottom: "20px", paddingLeft: "16px", paddingRight: "16px",
      display: "flex", alignItems: "center", gap: 10,
      flexShrink: 0, zIndex: 50,
    }}>
      {showBack && (
        <button
          onClick={() => screen === "document" ? onNavigateTo(navPath.length - 1) : onNavigateTo(navPath.length - 2)}
          style={{ background: "none", border: "none", cursor: "pointer", color: "#7BAAC8", display: "flex", padding: 4, flexShrink: 0 }}
        >
          <BackIcon />
        </button>
      )}
      {isRoot ? (
        <div style={{ flex: 1, display: "flex", justifyContent: "center" }}><Logo height={28} /></div>
      ) : (
        <div style={{ flex: 1, minWidth: 0, overflowX: "auto", scrollbarWidth: "none", display: "flex", alignItems: "center", gap: 4 }}>
          {crumbs.map((c, i) => (
            <span key={i} style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
              {i > 0 && <span style={{ color: "#C4BDB9", fontSize: 13 }}>›</span>}
              <span
                onClick={c.clickable ? () => onNavigateTo(c.depth) : undefined}
                style={{
                  fontFamily: "Outfit, sans-serif", fontSize: 13,
                  fontWeight: i === crumbs.length - 1 ? 700 : 400,
                  color: c.clickable ? "#7BAAC8" : "#2C2420",
                  cursor: c.clickable ? "pointer" : "default",
                  whiteSpace: "nowrap",
                  maxWidth: i === crumbs.length - 1 ? 160 : undefined,
                  overflow: i === crumbs.length - 1 ? "hidden" : undefined,
                  textOverflow: i === crumbs.length - 1 ? "ellipsis" : undefined,
                }}
              >
                {c.label}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
