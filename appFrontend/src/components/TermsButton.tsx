// Trigger only -- the real detected-terms/selection/simplify experience
// lives in TermsFoundScreen (reused as-is, screen === "terms-found" in
// App.tsx). This component owns no term data and no simplify logic, so
// there is exactly one implementation of that flow, not two.
export default function TermsButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        padding: "10px 18px", background: "#7BAAC8", color: "#fff",
        border: "none", borderRadius: 12, cursor: "pointer",
        fontFamily: "Outfit, sans-serif", fontSize: 14, fontWeight: 600,
        boxShadow: "0 2px 8px rgba(123,170,200,0.35)",
      }}
    >
      <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" stroke="#fff" strokeWidth={1.8} strokeLinecap="round" />
        <rect x="9" y="3" width="6" height="4" rx="1" stroke="#fff" strokeWidth={1.8} />
        <line x1="9" y1="12" x2="15" y2="12" stroke="#fff" strokeWidth={1.5} strokeLinecap="round" />
        <line x1="9" y1="16" x2="13" y2="16" stroke="#fff" strokeWidth={1.5} strokeLinecap="round" />
      </svg>
      View Detected Terms
    </button>
  );
}
