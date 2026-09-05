export function ActionTile({ icon, label, color, onClick, disabled }: { icon: React.ReactNode; label: string; color: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 7, padding: "16px 12px", background: "#fff", border: "1.5px solid #EDE9E5", borderRadius: 14, cursor: disabled ? "not-allowed" : "pointer", fontFamily: "Outfit, sans-serif", fontSize: 13, fontWeight: 500, color, opacity: disabled ? 0.5 : 1 }}
    >
      {icon}{label}
    </button>
  );
}
